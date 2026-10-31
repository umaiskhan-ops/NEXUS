"""Block 5 — Governance, Security & Safety (46 features named in the blueprint)."""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path

from ..sandbox import run_python
from ..security import Role
from ..state import cosine, tokenize
from .registry import Block, FeatureInputError, clamp, core, integration, llm, require_text

B = Block.GOVERNANCE
OWNER = Role.OWNER

_POSITIVE = {"good", "great", "thanks", "love", "excellent", "happy", "awesome", "perfect", "nice"}
_NEGATIVE = {"bad", "angry", "hate", "terrible", "awful", "broken", "frustrated", "annoyed", "useless", "worst"}
_URGENT = {"urgent", "asap", "now", "immediately", "emergency", "critical"}

INTENT_KEYWORDS = {
    "/status_grid": ("status", "health", "overview"),
    "/tasks": ("tasks", "missions", "queue"),
    "/features": ("features", "capabilities", "what can you do"),
    "/audit": ("audit", "verify ledger", "integrity"),
}


def _schedule(grid, p):
    op = p.get("op", "list")
    if op == "add":
        key = require_text(p, "feature")
        grid.registry.get(key)
        delay = float(p.get("delay_s", 60))
        payload = dict(p.get("feature_payload", {}))
        job = grid.scheduler.schedule(delay, lambda: grid.run_feature(grid.owner_tg_id, key, payload, via="scheduler"),
                                      label=key)
        return {"status": "SCHEDULED", "job_id": job, "due_in_s": delay}
    if op == "cancel":
        return {"status": "OK", "cancelled": grid.scheduler.cancel(require_text(p, "job_id"))}
    return {"status": "OK", "pending": grid.scheduler.pending()}


def _triggers(grid, p):
    op = p.get("op", "list")
    if op == "add":
        grid.registry.get(require_text(p, "feature"))
        tid = grid.triggers.register(require_text(p, "event"), p["feature"], dict(p.get("feature_payload", {})))
        return {"status": "REGISTERED", "trigger_id": tid, "events": "feature:<key>, task:approved, alert:<name>"}
    if op == "remove":
        return {"status": "OK", "removed": grid.triggers.remove(require_text(p, "trigger_id"))}
    return {"status": "OK", "triggers": grid.triggers.listing()}


def _workflow(grid, p):
    steps = p.get("steps")
    if not isinstance(steps, list) or not steps:
        raise FeatureInputError("'steps' must be a non-empty list of {feature, payload}")
    results = []
    for i, step in enumerate(steps[:20]):
        if not isinstance(step, dict) or not isinstance(step.get("feature"), str) or not step["feature"].strip():
            raise FeatureInputError(f"step {i + 1} must be a dict with a non-empty string 'feature'")
        raw_payload = step.get("payload") or {}
        if not isinstance(raw_payload, dict):
            raise FeatureInputError(f"step {i + 1} 'payload' must be a dict")
        res = grid.run_feature(grid.owner_tg_id, step["feature"], dict(raw_payload), via="workflow")
        results.append({"step": i + 1, "feature": step["feature"], "status": res.get("status")})
        if res.get("status") in {"ERROR", "DENIED", "BLOCKED", "PENDING_APPROVAL"}:
            return {"status": "HALTED", "at_step": i + 1, "results": results, "last": res}
    return {"status": "COMPLETED", "results": results}


def _error_recovery(grid, p):
    errors = [a for a in grid.action_log if a.get("status") == "ERROR"][-15:]
    return {"status": "OK", "policy": "transient backend errors retried once per node, then next node (fallback)",
            "recent_errors": errors}


def _self_opt(grid, p):
    stats = grid.feature_stats_summary()
    slow = sorted(stats.items(), key=lambda kv: kv[1]["avg_s"], reverse=True)[:5]
    suggestions = []
    if any(s["avg_s"] > 30 for _, s in slow):
        suggestions.append("Enable eco_mode or swap slow nodes to smaller quantized models.")
    if any(s["errors"] / max(1, s["calls"]) > 0.3 for s in stats.values()):
        suggestions.append("High error rates detected; check node health via /status_grid.")
    return {"status": "OK", "slowest": dict(slow), "suggestions": suggestions or ["No action needed."]}


def _nlu(grid, p):
    text = require_text(p).lower()
    for intent, kws in INTENT_KEYWORDS.items():
        if any(k in text for k in kws):
            return {"status": "OK", "intent": intent, "method": "keyword"}
    for f in grid.registry.all():
        if f.name.lower() in text or f.key.replace("_", " ") in text:
            return {"status": "OK", "intent": "/run", "feature": f.key, "method": "feature-name match"}
    return {"status": "OK", "intent": None, "suggestion": "Try /features or /run <feature_key> <text>"}


def _telegram(grid, p):
    return {"status": "OK", "bot_configured": bool(grid.config.telegram_bot_token),
            "webhook_url": grid.config.public_webhook_url or "(long-polling mode)",
            "webhook_secret_set": bool(grid.config.webhook_secret)}


def _dashboard(grid, p):
    return {"status": "OK", "enabled": bool(grid.config.dashboard_token),
            "url": f"http://{grid.config.host}:{grid.config.port}/dashboard (Bearer DASHBOARD_TOKEN)"}


def _report(grid, p):
    ok, bad = grid.ledger.verify()
    stats = grid.feature_stats_summary()
    report = "\n".join([
        f"# Grid Report — node {grid.node_id}",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Uptime: {int(time.time() - grid.started_at)} s",
        f"Ledger: {len(grid.ledger)} blocks, integrity {'OK' if ok else f'BROKEN at {bad}'}",
        f"Tasks: {len(grid.tasks.list())} total, {len(grid.tasks.list('QUEUED'))} queued",
        f"Feature calls: {sum(s['calls'] for s in stats.values())}, "
        f"errors: {sum(s['errors'] for s in stats.values())}",
        f"Budget: {grid.budget.status()}",
    ])
    path = grid.data_dir / "reports" / f"report_{int(time.time())}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")
    return {"status": "OK", "path": str(path), "report": report}


def _action_log(grid, p):
    return {"status": "OK", "entries": list(grid.action_log)[-clamp(p.get("n"), 1, 200, 20):]}


def _authorization(grid, p):
    uid = p.get("user_id")
    if uid is None:
        return {"status": "OK", "roles": grid.access.listing()}
    role = grid.access.role_of(int(uid))
    return {"status": "OK", "user_id": uid, "role": role.name if role else None}


def _encryption(grid, p):
    if not grid.encryption.available:
        return {"status": "UNAVAILABLE", "hint": "pip install cryptography"}
    if p.get("op") == "decrypt":
        return {"status": "OK", "plaintext": grid.encryption.decrypt(require_text(p, "token"))}
    return {"status": "OK", "token": grid.encryption.encrypt(require_text(p))}


def _kill_switch(grid, p):
    cancelled = grid.engage_kill_switch(reason=p.get("text", "kill switch"))
    return {"status": "KILL_SWITCH_ENGAGED", "cancelled_tasks": cancelled,
            "note": "Lockdown active. Use /emergency_override <passphrase> to restore."}


def _audit(grid, p):
    ok, bad = grid.ledger.verify()
    return {"status": "INTACT" if ok else "TAMPERED", "blocks": len(grid.ledger), "first_bad_index": bad,
            "head": grid.ledger.head_hash[:16]}


def _mission_control(grid, p):
    return {"status": "OK", "tasks": [t.to_dict() for t in grid.tasks.list()][-30:],
            "pending_approvals": [r.to_dict() for r in grid.approvals.pending()],
            "scheduled": grid.scheduler.pending()}


def _veto(grid, p):
    target = str(p.get("target_process_id", "ALL"))
    return {"status": "VETOED", **grid.veto(target)}


def _approval_gates(grid, p):
    op = p.get("op", "list")
    if op in {"approve", "reject"}:
        return grid.resolve_approval(require_text(p, "id"), op == "approve")
    return {"status": "OK", "pending": [r.to_dict() for r in grid.approvals.pending()]}


def _transparency(grid, p):
    return {"status": "OK", "blocks": grid.ledger.tail(clamp(p.get("n"), 1, 100, 10))}


def _override(grid, p):
    return {"status": "OK", "lockdown": grid.toggle_lockdown()}


def _shutdown(grid, p):
    grid.request_shutdown(reason=p.get("text", "owner shutdown"))
    return {"status": "SHUTDOWN_REQUESTED"}


def _access_control(grid, p):
    op = p.get("op", "list")
    if op in {"grant", "revoke"}:
        if "user_id" not in p:
            raise FeatureInputError("payload field 'user_id' (int) is required")
        try:
            uid = int(p["user_id"])
        except (TypeError, ValueError) as exc:
            raise FeatureInputError("payload field 'user_id' must be an integer") from exc
        if op == "grant":
            try:
                role = Role.parse(require_text(p, "role"))
            except ValueError as exc:
                raise FeatureInputError(str(exc)) from exc
            grid.access.grant(uid, role)
        else:
            grid.access.revoke(uid)
    return {"status": "OK", "roles": grid.access.listing()}


def _rollback(grid, p):
    name = p.get("snapshot") or grid.snapshots.latest()
    state = grid.snapshots.get(name) if name else None
    if state is None:
        return {"status": "NO_SNAPSHOT", "hint": "run state_snapshot_freeze first"}
    grid.restore_state(state)
    return {"status": "ROLLED_BACK", "snapshot": name}


def _testing_sandbox(grid, p):
    if not grid.config.enable_code_execution:
        return {"status": "DISABLED", "hint": "set ENABLE_CODE_EXECUTION=true"}
    import sys
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
                          cwd=root, capture_output=True, text=True, timeout=300)
    return {"status": "PASS" if proc.returncode == 0 else "FAIL", "output": (proc.stdout + proc.stderr)[-4000:]}


def _sim_rollback(grid, p):
    return _rollback(grid, {"snapshot": f"branch:{require_text(p, 'branch')}"})


def _autonomous(grid, p):
    if "enabled" in p:
        grid.autonomous_mode = bool(p["enabled"])
    return {"status": "OK", "autonomous_mode": grid.autonomous_mode,
            "note": "Autonomous mode lets queued tasks run without per-task prompts. Hardware and "
                    "self-improvement features stay approval-gated regardless."}


def _preferences(grid, p):
    if p.get("key"):
        grid.memory.set(f"pref:{p['key']}", p.get("value"), session="preferences")
    prefs = {k[5:]: grid.memory.get(k) for k in grid.memory.keys() if k.startswith("pref:")}
    return {"status": "OK", "preferences": prefs}


def _tone(grid, p):
    words = re.findall(r"[a-z']+", require_text(p).lower())
    pos, neg, urg = (sum(w in s for w in words) for s in (_POSITIVE, _NEGATIVE, _URGENT))
    tone = "positive" if pos > neg else "negative" if neg > pos else "neutral"
    return {"status": "OK", "tone": tone, "urgent": urg > 0, "scores": {"pos": pos, "neg": neg, "urgent": urg},
            "method": "lexicon (swap in a model via adapter for nuance)"}


def _dep_map(grid, p):
    graph = grid.registry.dependency_graph()
    return {"status": "OK", "edges": {k: v for k, v in graph.items() if v}}


def _hw_health(grid, p):
    usage = shutil.disk_usage(str(grid.data_dir))
    info = {"platform": platform.platform(), "python": platform.python_version(), "cpus": os.cpu_count(),
            "disk_free_gb": round(usage.free / 1e9, 2), "disk_total_gb": round(usage.total / 1e9, 2)}
    if hasattr(os, "getloadavg"):
        info["load_avg"] = os.getloadavg()
    try:
        import psutil  # optional
        info["mem_percent"] = psutil.virtual_memory().percent
        info["cpu_percent"] = psutil.cpu_percent(interval=0.2)
    except ImportError:
        info["note"] = "pip install psutil for CPU/RAM metrics"
    return {"status": "OK", **info}


def _deploy_selector(grid, p):
    need_gpu = bool(p.get("needs_gpu"))
    latency_ms = float(p.get("max_latency_ms", 500))
    private = bool(p.get("private_data", True))
    target = "edge" if private or latency_ms < 100 else "cloud" if need_gpu else "edge"
    return {"status": "OK", "target": target,
            "reasoning": {"private_data": private, "needs_gpu": need_gpu, "max_latency_ms": latency_ms}}


def _vcs(grid, p):
    if not shutil.which("git"):
        return {"status": "UNAVAILABLE", "hint": "git not installed"}
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(["git", "status", "--short", "--branch"], cwd=root, capture_output=True, text=True,
                          timeout=20)
    return {"status": "OK" if proc.returncode == 0 else "NOT_A_REPO", "output": (proc.stdout or proc.stderr)[-3000:]}


def _collab(grid, p):
    return {"status": "OK", "members": grid.access.listing(),
            "hint": "grant roles via access_control {op: grant, user_id, role: operator|observer}"}


def _scaling(grid, p):
    if "max_workers" in p:
        grid.set_worker_count(clamp(p["max_workers"], 1, 16, 1))
    return {"status": "OK", "workers": grid.worker_count, "queue_depth": grid.tasks.queue_depth()}


def _load_test(grid, p):
    n = clamp(p.get("requests"), 1, 500, 50)
    target = p.get("feature", "input_sanitization_layer")
    t0 = time.perf_counter()
    statuses = [grid.run_feature(grid.owner_tg_id, target, {"text": "load test"}, via="load_test", log=False)
                .get("status") for _ in range(n)]
    elapsed = time.perf_counter() - t0
    return {"status": "OK", "feature": target, "requests": n, "elapsed_s": round(elapsed, 3),
            "rps": round(n / elapsed, 1) if elapsed else None,
            "errors": sum(s in {"ERROR", "DENIED", "BLOCKED"} for s in statuses)}


def _monitor(grid, p):
    alerts = grid.check_alerts()
    return {"status": "ALERT" if alerts else "NOMINAL", "alerts": alerts}


def _backup(grid, p):
    return {"status": "OK", **grid.backup()}


def _disaster_recovery(grid, p):
    if p.get("op") == "restore":
        return {"status": "RESTORED", **grid.restore_backup(require_text(p, "backup"))}
    return {"status": "OK", "backups": grid.list_backups()}


def _constitution(grid, p):
    return {"status": "OK", "rules": [
        "no_destructive_commands (block)", "no_secret_exfiltration (block)",
        "human_approval_required for hardware & self-improvement (review)",
        "prompt_injection_review for LLM features (review)",
        "lockdown / kill switch halts all features except override",
        "frozen state blocks state-mutating features"]}


def _guardian(grid, p):
    blocked = [a for a in grid.action_log if a.get("status") in {"BLOCKED", "DENIED", "PENDING_APPROVAL"}][-20:]
    return {"status": "OK", "intercepted_actions": blocked, "intrusion_attempts": grid.intrusion_count}


def _human_review(grid, p):
    req = grid.approvals.request(p.get("feature", "manual_review"), dict(p.get("feature_payload", {})),
                                 grid.owner_tg_id, [p.get("text", "manual review requested")])
    return {"status": "PENDING_APPROVAL", "approval_id": req.id}


def _red_team(grid, p):
    saved_intrusions = grid.intrusion_count
    saved_log_len = len(grid.action_log)
    probes = [
        ("intruder", lambda: grid.process_telegram_inbound_signal(-1, "/status_grid", {})),
        ("unauthorised_veto", lambda: grid.run_feature(-1, "veto_power", {"target_process_id": "ALL"},
                                                       via="red_team", log=False)),
        ("destructive_payload", lambda: grid.run_feature(grid.owner_tg_id, "knowledge_synthesis",
                                                         {"text": "rm -rf / now"}, via="red_team", log=False)),
        ("hardware_without_approval", lambda: grid.run_feature(grid.owner_tg_id, "cnc_machine_control", {},
                                                               via="red_team", log=False)),
    ]
    expectations = {"intruder": lambda r: r.get("drop") is True,
                    "unauthorised_veto": lambda r: r.get("status") == "DENIED",
                    "destructive_payload": lambda r: r.get("status") == "BLOCKED",
                    "hardware_without_approval": lambda r: r.get("status") == "PENDING_APPROVAL"}
    results = {}
    for name, probe in probes:
        r = probe()
        results[name] = "DEFENDED" if expectations[name](r) else "FAILED"
    grid.intrusion_count = saved_intrusions
    while len(grid.action_log) > saved_log_len:
        grid.action_log.pop()
    grid.approvals_cleanup_red_team()
    return {"status": "PASS" if all(v == "DEFENDED" for v in results.values()) else "FAIL", "probes": results}


def _data_analysis(grid, p):
    data = p.get("data") or p.get("numbers", [])
    if isinstance(data, str):
        nums = [float(x) for x in re.findall(r"[-+]?(?:\d*\.\d+|\d+)", data)]
    elif isinstance(data, (list, tuple)):
        nums = [float(x) for x in data if isinstance(x, (int, float))]
    else:
        raise FeatureInputError("payload requires 'data' or 'numbers' as a list of numbers or formatted string")
    if not nums:
        raise FeatureInputError("no numerical values found in data")
    n = len(nums)
    s = sum(nums)
    mean = s / n
    sorted_nums = sorted(nums)
    median = (sorted_nums[n // 2] if n % 2 != 0 else (sorted_nums[n // 2 - 1] + sorted_nums[n // 2]) / 2)
    var = sum((x - mean) ** 2 for x in nums) / max(1, n - 1)
    std_dev = var ** 0.5
    return {
        "status": "OK",
        "count": n,
        "sum": round(s, 4),
        "mean": round(mean, 4),
        "median": round(median, 4),
        "min": round(min(nums), 4),
        "max": round(max(nums), 4),
        "std_dev": round(std_dev, 4),
    }


def _trend_forecasting(grid, p):
    nums = p.get("series") or p.get("data")
    if isinstance(nums, (list, tuple)):
        xs = [float(x) for x in nums if isinstance(x, (int, float)) and not isinstance(x, bool)]
        if len(xs) >= 2:
            n = len(xs)
            t = list(range(n))
            t_mean = sum(t) / n
            x_mean = sum(xs) / n
            denom = sum((ti - t_mean) ** 2 for ti in t)
            slope = sum((ti - t_mean) * (xi - x_mean) for ti, xi in zip(t, xs)) / (denom if denom != 0 else 1)
            forecast = [xs[-1] + slope * (step + 1) for step in range(clamp(p.get("steps", 3), 1, 10, 3))]
            direction = "UPWARD" if slope > 0.01 else "DOWNWARD" if slope < -0.01 else "FLAT"
            return {"status": "OK", "slope": round(slope, 4), "trend": direction, "projected": [round(f, 3) for f in forecast]}
    text = p.get("text", "")
    if not text:
        raise FeatureInputError("payload requires 'series' list of >=2 numbers or 'text' description")
    res = grid.router.ask(text, system="Analyze the trend and project probable future trajectory with confidence levels.")
    return {"status": "OK", "projection": res["text"]}


def _final_say(grid, p):
    decision = require_text(p, "decision")
    task_id = p.get("task_id", "GLOBAL")
    block = grid.ledger.append("final_say_executive_order", {
        "decision": decision,
        "task_id": task_id,
        "owner_id": grid.owner_tg_id,
        "timestamp": time.time(),
    })
    if task_id != "GLOBAL":
        t = grid.tasks.get(task_id)
        if t:
            t.status = "EXECUTED_BY_FINAL_SAY"
            t.result = {"executive_decision": decision}
    return {
        "status": "EXECUTIVE_RULING_RECORDED",
        "task_id": task_id,
        "decision": decision,
        "ledger_block": block["hash"][:16],
        "authority": "OWNER_ABSOLUTE",
    }


def _grid_state_rollback(grid, p):
    name = p.get("snapshot") or grid.snapshots.latest()
    if not name:
        return {"status": "NO_SNAPSHOT", "hint": "save snapshot first via state_snapshot_freeze"}
    state = grid.snapshots.get(name)
    if state is None:
        raise FeatureInputError(f"snapshot {name!r} not found")
    grid.restore_state(state)
    return {"status": "ROLLED_BACK", "snapshot": name}


def _code_testing_sandbox(grid, p):
    code = require_text(p, "code")
    timeout = float(p.get("timeout", 15.0))
    res = run_python(code, enabled=grid.config.enable_code_execution, timeout=timeout)
    return {"status": "OK" if res["ok"] else "TEST_FAILED", **res}


def _virtual_experiment_simulator(grid, p):
    sim_code = p.get("code")
    if sim_code:
        res = run_python(sim_code, enabled=grid.config.enable_code_execution, timeout=float(p.get("timeout", 10.0)))
        return {"status": "OK" if res["ok"] else "FAILED", **res}
    import random
    params = p.get("parameters") or {}
    try:
        trials = clamp(params.get("trials", 1000), 1, 1_000_000, 1000)
        runs = clamp(params.get("runs", 200), 1, 10_000, 200)
        rate = float(params.get("rate", 0.5))
    except (TypeError, ValueError) as exc:
        raise FeatureInputError("parameters: trials/runs must be ints, rate a float") from exc
    if not 0.0 <= rate <= 1.0:
        raise FeatureInputError("rate must be within [0, 1]")
    if trials * runs > 5_000_000:
        raise FeatureInputError("trials * runs must be <= 5,000,000")
    seed = params.get("seed", 42)
    rng = random.Random(seed)
    outcomes = sorted(sum(rng.random() < rate for _ in range(trials)) / trials for _ in range(runs))
    mean = sum(outcomes) / runs
    variance = sum((x - mean) ** 2 for x in outcomes) / max(1, runs - 1)
    pct = lambda q: outcomes[min(runs - 1, int(q * runs))]  # noqa: E731
    return {"status": "OK", "simulation": "monte_carlo_bernoulli",
            "parameters": {"trials": trials, "runs": runs, "rate": rate, "seed": seed},
            "distribution": {"mean": round(mean, 5), "variance": round(variance, 7),
                             "p05": round(pct(0.05), 5), "p50": round(pct(0.5), 5), "p95": round(pct(0.95), 5)}}


def _sliding_window_attention(grid, p):
    window_size = clamp(p.get("window_size", 10), 1, 100, 10)
    logs = list(grid.action_log)[-window_size:]
    summary_tokens = sum(len(str(entry)) // 4 for entry in logs)
    return {
        "status": "OK",
        "window_size": window_size,
        "captured_items": len(logs),
        "estimated_tokens": summary_tokens,
        "active_window": logs,
    }


def _hierarchical_memory_system(grid, p):
    op = p.get("op", "query")
    if op == "status":
        return {
            "status": "OK",
            "L1_working_keys": len(grid.memory.keys()),
            "L2_snapshots": len(grid.snapshots.names()),
            "L3_ledger_blocks": len(grid.ledger),
        }
    key = p.get("key", "")
    if op == "promote" and key:
        val = grid.memory.get(key)
        if val is not None:
            block = grid.ledger.append("memory_promoted_L3", {"key": key, "val": val})
            return {"status": "PROMOTED_TO_L3", "key": key, "block": block["hash"][:16]}
    return {"status": "OK", "hierarchy": {"L1": "RAM/KeyStore", "L2": "SnapshotManager", "L3": "HashChainLedger"}}


def _on_demand_memory_recall(grid, p):
    query = require_text(p, "query")
    k = clamp(p.get("k", 5), 1, 50, 5)
    mem_results = grid.memory.search(query, k=k)
    ledger_hits = []
    q_tokens = tokenize(query)
    for b in grid.ledger.tail(200):
        payload_str = str(b["data"]["payload"])
        score = cosine(q_tokens, tokenize(payload_str))
        if score > 0.1:
            ledger_hits.append({"hash": b["hash"][:16], "task": b["data"]["task"], "score": round(score, 3)})
    ledger_hits.sort(key=lambda x: x["score"], reverse=True)
    return {
        "status": "OK",
        "memory_hits": mem_results,
        "ledger_hits": ledger_hits[:k],
    }


FEATURES = [
    core("task_scheduling", "Task Scheduling", B, _schedule, "Delayed feature execution."),
    core("trigger_based_actions", "Trigger-Based Actions", B, _triggers, "event -> feature hooks"),
    core("workflow_automation", "Workflow Automation", B, _workflow, "Sequential multi-feature pipelines."),
    core("error_recovery", "Error Recovery", B, _error_recovery),
    core("self_optimization_loop", "Self-Optimization Loop", B, _self_opt),
    core("natural_language_understanding", "Natural Language Understanding", B, _nlu, "Free text -> intent."),
    llm("multi_language_support", "Multi-Language Support", B,
        "Translate the text. If no target language is specified, translate to English. Preserve meaning and tone."),
    core("telegram_interface_webhook", "Telegram Interface Webhook", B, _telegram),
    core("web_dashboard", "Web Dashboard", B, _dashboard),
    core("report_generation", "Report Generation", B, _report),
    core("action_logging", "Action Logging", B, _action_log),
    core("authorization_system", "Authorization System", B, _authorization),
    core("encryption_layer", "Encryption Layer", B, _encryption, "Fernet at-rest encryption."),
    core("kill_switch_protocol", "Kill Switch Protocol", B, _kill_switch, min_role=OWNER),
    core("audit_trail", "Audit Trail", B, _audit, "Ledger hash-chain verification."),
    core("mission_control", "Mission Control", B, _mission_control),
    core("veto_power", "Veto Power", B, _veto, min_role=OWNER),
    core("approval_gates", "Approval Gates", B, _approval_gates, min_role=OWNER),
    core("full_transparency_ledger", "Full Transparency Ledger", B, _transparency, min_role=Role.OBSERVER),
    core("emergency_override", "Emergency Override", B, _override, min_role=OWNER),
    core("shutdown_authority", "Shutdown Authority", B, _shutdown, min_role=OWNER),
    core("access_control", "Access Control", B, _access_control, min_role=OWNER),
    core("mission_change_rollbacks", "Mission Change Rollbacks", B, _rollback, min_role=OWNER),
    core("automated_testing_sandbox", "Automated Testing Sandbox", B, _testing_sandbox, min_role=OWNER),
    core("simulation_rollback", "Simulation Rollback", B, _sim_rollback,
         depends_on=("parallel_reality_branching",)),
    core("autonomous_mode_toggle", "Autonomous Mode Toggle", B, _autonomous, min_role=OWNER),
    core("user_preference_learning", "User Preference Learning", B, _preferences),
    core("emotional_tone_detection", "Emotional Tone Detection", B, _tone),
    core("dependency_mapping", "Dependency Mapping", B, _dep_map),
    integration("patent_publication_checker", "Patent/Publication Checker", B,
                "a patent/literature search API adapter (e.g. Lens.org, Semantic Scholar)"),
    llm("legal_compliance_checker", "Legal Compliance Checker", B,
        "Flag potential legal/regulatory compliance issues in the described activity and which regimes may apply. "
        "State clearly that this is not legal advice and a qualified lawyer must review."),
    integration("multimodal_input", "Multimodal Input", B, "a vision-capable local model adapter (e.g. llava)"),
    integration("stt_tts_engine", "STT/TTS Engine", B, "a local speech adapter (e.g. whisper.cpp + piper)"),
    core("hardware_health_monitor", "Hardware Health Monitor", B, _hw_health),
    core("cloud_edge_deployment_selector", "Cloud/Edge Deployment Selector", B, _deploy_selector),
    core("version_control_integration", "Version Control Integration", B, _vcs),
    core("multi_user_collaboration", "Multi-User Collaboration", B, _collab),
    core("gradual_scaling_controller", "Gradual Scaling Controller", B, _scaling, min_role=OWNER),
    core("load_testing_engine", "Load Testing Engine", B, _load_test, min_role=OWNER),
    core("realtime_monitor_alert_grid", "Real-Time Monitor & Alert Grid", B, _monitor),
    core("disaster_recovery_manager", "Disaster Recovery Manager", B, _disaster_recovery, min_role=OWNER,
         depends_on=("redundant_backup_system",)),
    core("redundant_backup_system", "Redundant Backup System", B, _backup, min_role=OWNER),
    core("constitutional_rule_enforcer", "Constitutional Rule Enforcer", B, _constitution),
    core("guardian_ai_monitor", "Guardian AI Monitor", B, _guardian),
    core("human_review_gate", "Human Review Gate", B, _human_review),
    core("red_team_safety_tester", "Red-Team Safety Tester", B, _red_team, min_role=OWNER),
    # Extended 17 Features (bringing Block 5 to 63, and the total system matrix to 130 features)
    core("data_analysis", "Data Analysis", B, _data_analysis, "Statistical calculations and distribution analysis."),
    llm("risk_assessment", "Risk Assessment", B,
        "Perform a comprehensive risk assessment: likelihood (1-5), impact (1-5), severity score, and mitigations."),
    llm("impact_prediction", "Impact Prediction", B,
        "Evaluate direct, indirect, and second-order systemic impacts across short, medium, and long term horizons."),
    core("trend_forecasting", "Trend Forecasting", B, _trend_forecasting, "Linear slope projection and trend modeling."),
    llm("root_cause_analysis", "Root Cause Analysis", B,
        "Perform 5-Whys and Ishikawa root cause analysis to trace symptoms to foundational issues."),
    core("final_say_protocol", "Final Say Protocol", B, _final_say,
         "Owner absolute executive ruling overriding swarm consensus and gates.", min_role=OWNER),
    core("grid_state_rollback", "Grid State Rollback", B, _grid_state_rollback,
         "Rollback system memory and configuration to a previous snapshot.", min_role=OWNER),
    integration("formal_proof_verification", "Formal Proof Verification", B,
                "an interactive theorem prover bridge (e.g. Lean 4, Coq, or Z3)"),
    llm("mathematical_gap_detection", "Mathematical Gap Detection", B,
        "Scrutinize mathematical derivations step-by-step for subtle logical gaps and unstated assumptions."),
    core("automated_code_testing_sandbox", "Automated Code Testing Sandbox", B, _code_testing_sandbox,
         "Execute test suites inside isolated Python runner.", depends_on=("automated_testing_sandbox",)),
    llm("hypothesis_tester", "Hypothesis Tester", B,
        "Assess experimental data against hypotheses to determine validation or falsification."),
    core("virtual_experiment_simulator", "Virtual Experiment Simulator", B, _virtual_experiment_simulator,
         "Virtual parameter sweep and Monte Carlo simulation harness."),
    llm("journal_submission_assistant", "Journal Submission Assistant", B,
        "Format academic papers, prepare cover letters, and draft reviewer response matrices."),
    core("sliding_window_attention", "Sliding Window Attention", B, _sliding_window_attention,
         "Manage rolling window of recent execution logs and context token metrics."),
    core("hierarchical_memory_system", "Hierarchical Memory System", B, _hierarchical_memory_system,
         "Multi-tier memory: L1 working cache, L2 snapshots, and L3 immutable ledger."),
    llm("conversation_summarizer", "Conversation Summarizer", B,
        "Compress multi-turn dialogue into high-density state representations and action items."),
    core("on_demand_memory_recall", "On-Demand Memory Recall", B, _on_demand_memory_recall,
         "Unified dual-tier search querying both active memory and past ledger blocks."),
]
