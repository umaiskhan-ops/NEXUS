"""UltimateAgiSovereignGrid — node runtime: security pipeline, feature dispatch, Telegram intents,
task workers, monitoring, backups and peer status."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
import re
import shutil
import threading
import time
import urllib.request
import uuid
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .config import GridConfig
from .features import Block, FeatureInputError, Kind, build_registry
from .hub_spoke import LightweightWorkerNode, MasterHubCoordinator
from .ledger import HashChainLedger
from .models import BackendUnavailable, LLMBackend, ModelNode, ModelRouter, OllamaBackend
from .security import (AccessControl, AuthGuard, ConstitutionalRuleEnforcer, EncryptionLayer, Role,
                       sanitize_payload)
from .state import (ApprovalQueue, BudgetExceeded, MemoryStore, Scheduler, SnapshotManager, TaskRegistry,
                    TokenBudget, TriggerEngine)

# Features that additionally require the master passphrase (restoring control must be hard; stopping is easy).
PASSPHRASE_FEATURES = {"veto_power", "emergency_override", "access_control", "mission_change_rollbacks",
                       "disaster_recovery_manager", "autonomous_mode_toggle", "final_say_protocol",
                       "grid_state_rollback"}
# Features that mutate state and are blocked while the grid is frozen.
STATE_MUTATING = {"local_memory_management", "cross_session_memory_fusion", "user_preference_learning",
                  "parallel_reality_branching", "mission_change_rollbacks", "simulation_rollback",
                  "disaster_recovery_manager", "quantized_model_hot_swap", "precision_scalability_switch",
                  "access_control", "cad_stl_output", "grid_state_rollback"}
LOCKDOWN_ALLOWED = {"emergency_override", "audit_trail", "full_transparency_ledger"}
_BACKUP_NAME = re.compile(r"^\d{8}-\d{6}$")


class UltimateAgiSovereignGrid:
    def __init__(self, config: GridConfig, backend: Optional[LLMBackend] = None):
        self.config = config
        self.data_dir = Path(config.data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.node_id = self._load_node_id()
        self.owner_tg_id = config.owner_telegram_id
        self.started_at = time.time()

        self.auth = AuthGuard(config.master_passphrase_hash)
        self.access = AccessControl(config.owner_telegram_id, config.collaborators)
        self.rules = ConstitutionalRuleEnforcer([config.telegram_bot_token, config.webhook_secret,
                                                 config.dashboard_token, config.peer_shared_secret])
        self.encryption = EncryptionLayer(self.data_dir / "fernet.key")

        self.ledger = HashChainLedger(self.data_dir / "ledger.jsonl")
        self.memory = MemoryStore(self.data_dir / "memory.json")
        self.snapshots = SnapshotManager()
        self.budget = TokenBudget(config.token_budget)
        self.tasks = TaskRegistry()
        self.scheduler = Scheduler()
        self.approvals = ApprovalQueue()
        self.triggers = TriggerEngine()
        self.hub = MasterHubCoordinator(self.ledger, grid=self, state_path=self.data_dir / "hub_workers.json")

        nodes = [ModelNode(m["name"], m["role"], m["model"]) for m in config.mesh]
        self.router = ModelRouter(nodes, backend or OllamaBackend(config.ollama_url), self.budget,
                                  config.llm_timeout_s)
        self.registry = build_registry()
        self.adapters: Dict[str, Callable[[Any, dict], dict]] = {}

        self.system_lockdown = False
        self.frozen = False
        self.autonomous_mode = False
        self.silent_observer = False
        self.partial_failure_tolerant = True
        self.intrusion_count = 0
        self.action_log: deque = deque(maxlen=2000)
        self._stats: Dict[str, dict] = defaultdict(lambda: {"calls": 0, "errors": 0, "total_s": 0.0})
        self._stats_lock = threading.Lock()
        self._red_team_approvals: List[str] = []
        self._last_alerts: set = set()

        self.notifier: Optional[Callable[[str], None]] = None  # set by the Telegram gateway
        self.shutdown_event = threading.Event()
        self._workers: List[threading.Thread] = []
        self._desired_workers = 1
        self._started = False
        print(f"[GRID] Sovereign mesh node {self.node_id} initialised | {len(self.registry)} features | "
              f"{len(nodes)} local model nodes")

    # ------------------------------------------------------------ lifecycle
    def _load_node_id(self) -> str:
        path = self.data_dir / "node_id"
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
        nid = str(uuid.uuid4())
        path.write_text(nid, encoding="utf-8")
        return nid

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self.scheduler.start()
        self.set_worker_count(self._desired_workers)
        threading.Thread(target=self._monitor_loop, name="monitor", daemon=True).start()

    def stop(self) -> None:
        self.shutdown_event.set()
        self.scheduler.stop()

    def register_adapter(self, feature_key: str, fn: Callable[[Any, dict], dict]) -> None:
        self.adapters[self.registry.get(feature_key).key] = fn

    @property
    def worker_count(self) -> int:
        return len([w for w in self._workers if w.is_alive()])

    def set_worker_count(self, n: int) -> None:
        self._desired_workers = n
        if not self._started:
            return
        self._workers = [w for w in self._workers if w.is_alive()]
        while len(self._workers) < n:
            t = threading.Thread(target=self._worker_loop, args=(len(self._workers),),
                                 name=f"worker-{len(self._workers)}", daemon=True)
            self._workers.append(t)
            t.start()

    def _worker_loop(self, idx: int) -> None:
        while not self.shutdown_event.is_set():
            if idx >= self._desired_workers:  # gradual scale-down
                return
            if self.system_lockdown:
                time.sleep(1.0)
                continue
            task = self.tasks.next(timeout=1.0)
            if not task:
                continue
            feature = task.payload.get("feature")
            if feature:
                res = self.run_feature(task.created_by, feature, dict(task.payload.get("feature_payload", {})),
                                       via=f"task:{task.id}")
                task.result = res
                if task.cancel_event.is_set():
                    task.status = "VETOED"
                else:
                    task.status = "DONE" if res.get("status") not in {"ERROR", "BLOCKED", "DENIED"} else "FAILED"
            else:
                task.status = "DONE"
            self.ledger.append("task_completed", {"task_id": task.id, "status": task.status})
            self._notify(f"Task {task.id} ({task.name}) finished: {task.status}")

    def _monitor_loop(self) -> None:
        while not self.shutdown_event.wait(60.0):
            alerts = set(self.check_alerts())
            new = alerts - self._last_alerts
            self._last_alerts = alerts
            for a in sorted(new):
                self._notify(f"ALERT: {a}")
                self._fire_triggers(f"alert:{a}")

    def _notify(self, text: str) -> None:
        if self.notifier and not self.silent_observer:
            try:
                self.notifier(text)
            except Exception:  # noqa: BLE001 - notifications are best-effort
                pass

    # ------------------------------------------------------------ state helpers
    def capture_state(self) -> dict:
        return {"memory": self.memory.export(),
                "flags": {"autonomous_mode": self.autonomous_mode, "silent_observer": self.silent_observer,
                          "partial_failure_tolerant": self.partial_failure_tolerant,
                          "eco_mode": self.router.eco_mode, "silent_fallback": self.router.silent_fallback},
                "mesh": {n.name: n.model for n in self.router.nodes}}

    def restore_state(self, state: dict) -> None:
        self.memory.load(state.get("memory", {}))
        flags = state.get("flags", {})
        self.autonomous_mode = flags.get("autonomous_mode", self.autonomous_mode)
        self.silent_observer = flags.get("silent_observer", self.silent_observer)
        self.partial_failure_tolerant = flags.get("partial_failure_tolerant", self.partial_failure_tolerant)
        self.router.eco_mode = flags.get("eco_mode", self.router.eco_mode)
        self.router.silent_fallback = flags.get("silent_fallback", self.router.silent_fallback)
        for name, model in state.get("mesh", {}).items():
            node = self.router.node(name)
            if node:
                node.model = model
        self.ledger.append("state_restored", {"keys": len(self.memory.keys())})

    def feature_stats_summary(self) -> Dict[str, dict]:
        with self._stats_lock:
            return {k: {"calls": v["calls"], "errors": v["errors"],
                        "avg_s": round(v["total_s"] / v["calls"], 4) if v["calls"] else 0.0}
                    for k, v in self._stats.items()}

    def session_fingerprint(self) -> dict:
        raw = f"{self.node_id}|{self.started_at}|{os.getpid()}|{platform.node()}|{platform.python_version()}"
        return {"session": hashlib.sha256(raw.encode()).hexdigest()[:24], "node_id": self.node_id,
                "started_at": self.started_at, "pid": os.getpid()}

    # ------------------------------------------------------------ control actions
    def engage_kill_switch(self, reason: str) -> List[str]:
        cancelled = self.tasks.cancel("ALL")
        self.system_lockdown = True
        self.autonomous_mode = False
        self.ledger.append("kill_switch", {"reason": reason, "cancelled": cancelled})
        return cancelled

    def toggle_lockdown(self) -> bool:
        self.system_lockdown = not self.system_lockdown
        self.ledger.append("lockdown_toggled", {"lockdown": self.system_lockdown})
        return self.system_lockdown

    def request_shutdown(self, reason: str) -> None:
        self.tasks.cancel("ALL")
        self.ledger.append("shutdown", {"reason": reason})
        threading.Timer(2.0, self.stop).start()  # let the reply go out first

    def veto(self, target: str) -> dict:
        cancelled = self.tasks.cancel(target)
        block = self.ledger.append("veto", {"target": target, "cancelled": cancelled})
        return {"target": target, "cancelled": cancelled, "ledger_block": block["hash"][:16],
                "note": "Ledger is append-only: the veto is recorded as a compensating block."}

    def resolve_approval(self, req_id: str, approve: bool) -> dict:
        req = self.approvals.resolve(req_id, approve)
        if not req:
            return {"status": "NOT_FOUND", "id": req_id}
        self.ledger.append("approval_resolved", {"id": req_id, "feature": req.feature_key, "approved": approve})
        if not approve:
            return {"status": "REJECTED", "id": req_id}
        result = self.run_feature(req.requested_by, req.feature_key, dict(req.payload), via="approval",
                                  approved=True)
        return {"status": "APPROVED_AND_EXECUTED", "id": req_id, "result": result}

    def approvals_cleanup_red_team(self) -> None:
        for rid in self._red_team_approvals:
            self.approvals.resolve(rid, False)
        self._red_team_approvals.clear()

    # ------------------------------------------------------------ monitoring / backups / peers
    def check_alerts(self) -> List[str]:
        alerts = []
        ok, _ = self.ledger.verify()
        if not ok:
            alerts.append("ledger_integrity_failure")
        if not self.router.eligible_nodes():
            alerts.append("no_eligible_model_nodes")
        if self.budget.available < 0.05 * self.budget.total:
            alerts.append("token_budget_low")
        usage = shutil.disk_usage(str(self.data_dir))
        if usage.free / usage.total < 0.05:
            alerts.append("disk_space_low")
        if self.system_lockdown:
            alerts.append("lockdown_active")
        if len(self.approvals.pending()) > 0:
            alerts.append("approvals_pending")
        return alerts

    def backup(self) -> dict:
        name = time.strftime("%Y%m%d-%H%M%S")
        targets = [self.data_dir / "backups" / name]
        mirror = os.environ.get("BACKUP_MIRROR_DIR")
        if mirror:
            targets.append(Path(mirror) / self.node_id / name)
        for dest in targets:
            dest.mkdir(parents=True, exist_ok=True)
            for fname in ("ledger.jsonl", "memory.json", "node_id"):
                src = self.data_dir / fname
                if src.exists():
                    shutil.copy2(src, dest / fname)
        self.ledger.append("backup", {"name": name, "copies": len(targets)})
        return {"backup": name, "copies": [str(t) for t in targets]}

    def list_backups(self) -> List[str]:
        root = self.data_dir / "backups"
        return sorted(p.name for p in root.iterdir() if p.is_dir()) if root.exists() else []

    def restore_backup(self, name: str) -> dict:
        if not _BACKUP_NAME.match(name):
            raise FeatureInputError("invalid backup name")
        src = self.data_dir / "backups" / name
        if not src.is_dir():
            raise FeatureInputError(f"backup {name} not found")
        candidate = HashChainLedger(src / "ledger.jsonl")
        ok, bad = candidate.verify()
        if not ok:
            raise FeatureInputError(f"backup ledger is corrupt at block {bad}; refusing to restore")
        self.backup()  # safety copy of current state first
        for fname in ("ledger.jsonl", "memory.json"):
            if (src / fname).exists():
                shutil.copy2(src / fname, self.data_dir / fname)
        self.ledger = HashChainLedger(self.data_dir / "ledger.jsonl")
        self.memory = MemoryStore(self.data_dir / "memory.json")
        self.ledger.append("disaster_recovery_restore", {"backup": name})
        return {"backup": name, "ledger_blocks": len(self.ledger)}

    def peer_signature(self, timestamp: str) -> str:
        return hmac.new(self.config.peer_shared_secret.encode(), timestamp.encode(), hashlib.sha256).hexdigest()

    def peer_status(self, timeout: float = 3.0) -> List[dict]:
        out = []
        for peer in self.config.peers:
            ts = str(int(time.time()))
            req = urllib.request.Request(peer["url"].rstrip("/") + "/p2p/head",
                                         headers={"X-Peer-Timestamp": ts, "X-Peer-Signature": self.peer_signature(ts)})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    out.append({"peer": peer.get("name", peer["url"]), "reachable": True, **json.loads(resp.read())})
            except Exception as exc:  # noqa: BLE001
                out.append({"peer": peer.get("name", peer["url"]), "reachable": False, "error": str(exc)[:120]})
        return out

    # ------------------------------------------------------------ feature dispatch pipeline
    def _record(self, entry: dict, log: bool) -> None:
        if log:
            self.action_log.append(entry)

    def _fire_triggers(self, event: str) -> None:
        for trig in self.triggers.matching(event):
            threading.Thread(target=self.run_feature, daemon=True,
                             args=(self.owner_tg_id, trig["feature"], dict(trig["payload"])),
                             kwargs={"via": f"trigger:{event}"}).start()

    def run_feature(self, sender_id: int, key: str, payload: Optional[dict] = None, via: str = "direct",
                    approved: bool = False, passphrase: Optional[str] = None, log: bool = True) -> dict:
        payload = dict(payload or {})
        payload.pop("passphrase", None)  # never let secrets reach handlers, logs or the ledger
        entry = {"ts": time.time(), "sender": sender_id, "feature": key, "via": via}

        def finish(result: dict) -> dict:
            entry["status"] = result.get("status")
            self._record(entry, log)
            return result

        try:
            feature = self.registry.get(key)
        except KeyError:
            return finish({"status": "ERROR", "error": f"unknown feature '{key}'"})
        entry["feature"] = feature.key

        # 1. lockdown / freeze
        if self.system_lockdown and feature.key not in LOCKDOWN_ALLOWED:
            return finish({"status": "DENIED", "error": "system lockdown active"})
        if self.frozen and feature.key in STATE_MUTATING:
            return finish({"status": "DENIED", "error": "state is frozen (state_snapshot_freeze)"})
        # 2. access control
        if not self.access.allows(sender_id, feature.min_role):
            return finish({"status": "DENIED", "error": f"requires role {feature.min_role.name}"})
        # 3. passphrase gate
        if feature.key in PASSPHRASE_FEATURES and not approved:
            ok, reason = self.auth.verify(passphrase)
            if not ok:
                return finish({"status": "DENIED", "error": f"passphrase verification failed ({reason})"})
        # 4. sanitization + constitutional / guardian checks
        clean, flags = sanitize_payload(payload)
        violations = self.rules.check(feature.kind.value, feature.requires_approval, approved, clean, flags)
        blocking = [v for v in violations if v[1] == "block"]
        if blocking:
            self.ledger.append("guardian_block", {"feature": feature.key, "rules": [v[0] for v in blocking]})
            return finish({"status": "BLOCKED", "violations": [v[0] for v in blocking]})
        review = [v for v in violations if v[1] == "review"]
        if review:
            req = self.approvals.request(feature.key, clean, sender_id, [v[2] for v in review])
            if via == "red_team":
                self._red_team_approvals.append(req.id)
            else:
                self._notify(f"Approval needed [{req.id}] for {feature.name}: {'; '.join(v[2] for v in review)}\n"
                             f"Reply /approve {req.id} or /reject {req.id}")
            return finish({"status": "PENDING_APPROVAL", "approval_id": req.id, "reasons": [v[2] for v in review]})
        # 5. execute with error isolation
        t0 = time.perf_counter()
        try:
            result = feature.handler(self, clean)
            if not isinstance(result, dict):  # output format enforcement
                result = {"status": "OK", "output": result}
            result.setdefault("status", "OK")
            if flags:
                result["input_flags"] = flags
        except FeatureInputError as exc:
            result = {"status": "ERROR", "error": f"bad input: {exc}"}
        except (BackendUnavailable, BudgetExceeded) as exc:
            result = {"status": "ERROR", "error": str(exc)[:500],
                      "hint": "Is Ollama running and are the models pulled? See README."}
        except Exception as exc:  # noqa: BLE001 - a broken feature must never crash the node
            result = {"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"[:500]}
        elapsed = time.perf_counter() - t0
        with self._stats_lock:
            st = self._stats[feature.key]
            st["calls"] += 1
            st["total_s"] += elapsed
            st["errors"] += result["status"] == "ERROR"
        if log and via not in {"load_test", "red_team"}:
            self.ledger.append(f"feature:{feature.key}", {"via": via, "sender": sender_id,
                                                          "status": result["status"]})
            self._fire_triggers(f"feature:{feature.key}")
        return finish(result)

    # ------------------------------------------------------------ Telegram intent gateway
    HELP = ("Commands:\n/status_grid\n/features [block]\n/run <feature_key> <text | json>\n"
            "/execute_autonomous_task <name> [| json]\n/tasks\n/models\n"
            "/add_model <name> <role> <model_tag>\n/remove_model <name>\n"
            "/workers\n/register_worker <id> [url]\n/dispatch_worker <id> <feature> <payload>\n"
            "/approve <id> | /reject <id>\n/audit\n"
            "/kill_switch [reason]\n/shutdown\n/federal_veto <task_id|ALL> <passphrase>\n"
            "/emergency_override <passphrase>")

    def process_telegram_inbound_signal(self, sender_id: int, intent: str, command_payload: Optional[dict] = None,
                                        master_key_verification: Optional[str] = None) -> dict:
        """Main gateway mapping Telegram commands onto grid features."""
        payload = dict(command_payload or {})
        role = self.access.role_of(sender_id)

        # Step 1: intruder mitigation — unknown senders get no reply at all.
        if role is None:
            self.intrusion_count += 1
            self.action_log.append({"ts": time.time(), "sender": sender_id, "intent": intent, "status": "INTRUSION"})
            return {"tele_response": None, "drop": True, "alert": "HIGH"}

        if self.system_lockdown and intent not in {"/emergency_override", "/status_grid", "/audit"}:
            return {"tele_response": "🔒 SYSTEM LOCKDOWN ACTIVE: all features frozen. "
                                     "Use /emergency_override <passphrase>.", "status": "LOCKED"}

        if intent in {"/start", "/help"}:
            return {"tele_response": self.HELP}

        if intent == "/status_grid":
            ok, _ = self.ledger.verify()
            nodes = "\n".join(f"  • {n.name} [{n.role}] {n.model}: {n.status}" for n in self.router.nodes)
            kinds = self.registry.kind_counts()
            return {"tele_response": (
                f"📊 SOVEREIGN MESH OVERVIEW\nNode: {self.node_id}\nModel nodes:\n{nodes}\n"
                f"Features: {len(self.registry)} ({kinds['core']} core, {kinds['llm']} llm, "
                f"{kinds['integration']} integration hooks, {kinds['hardware']} hardware hooks)\n"
                f"Ledger: {len(self.ledger)} blocks ({'intact' if ok else 'TAMPERED'})\n"
                f"Tasks queued: {self.tasks.queue_depth()} | Approvals pending: {len(self.approvals.pending())}\n"
                f"Peers configured: {len(self.config.peers)}\n"
                f"Lockdown: {self.system_lockdown} | Autonomous: {self.autonomous_mode}\n"
                f"Status: {'LOCKED' if self.system_lockdown else 'OPERATIONAL'}")}

        if intent == "/features":
            block = payload.get("block")
            blocks = [b for b in Block if not block or block in b.value]
            lines = []
            for b in blocks:
                feats = self.registry.by_block(b)
                lines.append(f"\n[{b.value}] ({len(feats)})")
                lines += [f"  {f.key} ({f.kind.value})" for f in feats] if block else []
            return {"tele_response": f"Features: {len(self.registry)}" + "\n".join(lines) +
                                     ("" if block else "\n\nUse /features <block> for keys.")}

        if intent == "/run":
            key = payload.pop("feature", "")
            res = self.run_feature(sender_id, key, payload, via="telegram", passphrase=master_key_verification)
            return {"tele_response": f"[{key}] {res.get('status')}\n" +
                                     json.dumps(res, indent=1, default=str)[:3500], "result": res}

        if intent == "/execute_autonomous_task":
            if role < Role.OPERATOR:
                return {"tele_response": "❌ Operator role required."}
            return self._execute_autonomous_task(sender_id, payload)

        if intent == "/tasks":
            tasks = self.tasks.list()[-15:]
            body = "\n".join(f"{t.id} {t.status:<9} p{t.priority} {t.name}" for t in tasks) or "(none)"
            return {"tele_response": f"Tasks:\n{body}"}

        if intent in {"/approve", "/reject"}:
            res = self.run_feature(sender_id, "approval_gates",
                                   {"op": intent[1:], "id": payload.get("id", "")}, via="telegram")
            return {"tele_response": f"{intent[1:].upper()}: " + json.dumps(res, default=str)[:3500]}

        if intent == "/audit":
            res = self.run_feature(sender_id, "audit_trail", {}, via="telegram")
            return {"tele_response": f"🧾 Audit: {res.get('status')} — {res.get('blocks')} blocks, "
                                     f"head {res.get('head')}"}

        if intent == "/models":
            active = "\n".join(f"  • {n.name} [{n.role}] -> {n.model} ({n.status})" for n in self.router.nodes)
            available = self.router.available_models()
            avail_str = ", ".join(available) if available else "(backend idle / none listed)"
            return {"tele_response": f"🤖 ACTIVE SWARM NODES ({len(self.router.nodes)}):\n{active}\n\n"
                                     f"📦 DISCOVERED IN BACKEND:\n{avail_str}\n\n"
                                     f"Use /add_model <name> <role> <model_tag> to register a new model."}

        if intent == "/add_model":
            if role is not Role.OWNER:
                return {"tele_response": "❌ Owner role required to add models."}
            name = payload.get("name")
            model_tag = payload.get("model")
            model_role = payload.get("role", "Validator")
            if not name or not model_tag:
                return {"tele_response": "❌ Usage: /add_model <name> <role> <model_tag>\n"
                                         "Example: /add_model Qwen-Coder Coder qwen2.5-coder:7b"}
            res = self.router.add_node(name, model_role, model_tag)
            self.ledger.append("model_added", res)
            return {"tele_response": f"✅ Model node registered into mesh:\n{json.dumps(res, indent=1)}"}

        if intent == "/remove_model":
            if role is not Role.OWNER:
                return {"tele_response": "❌ Owner role required to remove models."}
            name = payload.get("name") or payload.get("text")
            if not name:
                return {"tele_response": "❌ Usage: /remove_model <node_name>"}
            try:
                res = self.router.remove_node(name)
                self.ledger.append("model_removed", res)
                return {"tele_response": f"🗑️ Model node removed: {name}"}
            except KeyError:
                return {"tele_response": f"❌ Unknown node: {name}"}

        if intent == "/workers":
            workers = self.hub.list_workers()
            if not workers:
                return {"tele_response": "🌐 No edge worker nodes registered. Use /register_worker <id> [url]"}
            lines = [f"  • {w['worker_id']} [{w['status']}] Credits: {w['credits']} "
                     f"(Burned: {w['burned_credits']}) Tasks: {w['tasks_completed']}" for w in workers]
            return {"tele_response": f"🌐 EDGE WORKER NODES ({len(workers)}):\n" + "\n".join(lines)}

        if intent == "/register_worker":
            if role is not Role.OWNER:
                return {"tele_response": "❌ Owner role required to register workers."}
            wid = payload.get("worker_id") or payload.get("text")
            if not wid:
                return {"tele_response": "❌ Usage: /register_worker <worker_id> [url]"}
            try:
                rec = self.hub.register_worker(wid, payload.get("url", "local"))
                return {"tele_response": f"✅ Worker registered: {rec.worker_id} (Initial stake: {rec.credits} credits)",
                        "worker_key": rec.key}
            except (PermissionError, ValueError) as exc:
                return {"tele_response": f"❌ {exc}"}

        if intent == "/dispatch_worker":
            if role is not Role.OWNER:
                return {"tele_response": "❌ Owner role required to dispatch hub tasks."}
            wid = payload.get("worker_id", "")
            fkey = payload.get("feature", "")
            task_payload = payload.get("task_payload", {})
            if not wid or not fkey:
                return {"tele_response": "❌ Usage: /dispatch_worker <worker_id> <feature_key> <text_or_json>"}
            try:
                wrec = self.hub.get_worker(wid)
                if wrec and wrec.url != "local":
                    settlement = self.hub.dispatch_remote(wid, fkey, task_payload)
                else:
                    signed_task = self.hub.create_signed_task(wid, fkey, task_payload)
                    worker_node = LightweightWorkerNode(wid, self.hub.worker_key(wid), self)
                    response_packet = worker_node.execute_signed_task(signed_task)
                    settlement = self.hub.verify_and_settle(response_packet)
                return {"tele_response": f"⚡ HUB-AND-SPOKE SETTLEMENT [{settlement['status']}]:\n"
                                         f"{json.dumps(settlement, indent=1, default=str)[:3500]}",
                        "settlement": settlement}
            except (KeyError, PermissionError, ValueError) as exc:
                return {"tele_response": f"❌ Dispatch rejected: {exc}"}

        if intent == "/kill_switch":
            res = self.run_feature(sender_id, "kill_switch_protocol", {"text": payload.get("text", "telegram")},
                                   via="telegram")
            return {"tele_response": f"🛑 {res.get('status')}: cancelled {len(res.get('cancelled_tasks', []))} tasks. "
                                     f"{res.get('note', res.get('error', ''))}"}

        if intent == "/shutdown":
            res = self.run_feature(sender_id, "shutdown_authority", {}, via="telegram")
            return {"tele_response": f"⏻ {res.get('status')} {res.get('error', '')}"}

        if intent == "/federal_veto":
            if not master_key_verification:
                return {"tele_response": "🔑 AUTHENTICATION REQUIRED: /federal_veto <task_id|ALL> <passphrase>"}
            res = self.run_feature(sender_id, "veto_power",
                                   {"target_process_id": payload.get("target_process_id", "ALL")},
                                   via="telegram", passphrase=master_key_verification)
            if res.get("status") == "VETOED":
                return {"tele_response": f"🛡️ VETO EXECUTED: target {res['target']}, cancelled "
                                         f"{len(res['cancelled'])} task(s). Ledger block {res['ledger_block']}."}
            return {"tele_response": f"❌ ACCESS DENIED: {res.get('error', 'invalid signature')}"}

        if intent == "/emergency_override":
            if self.access.role_of(sender_id) is not Role.OWNER:
                return {"tele_response": "❌ Owner only."}
            # Bypasses the lockdown gate by design; passphrase is the gate.
            ok, reason = self.auth.verify(master_key_verification)
            if not ok:
                self.action_log.append({"ts": time.time(), "sender": sender_id, "feature": "emergency_override",
                                        "status": "DENIED"})
                return {"tele_response": f"❌ CRITICAL: unauthorized override attempt blocked ({reason})."}
            state = self.toggle_lockdown()
            return {"tele_response": f"🚨 EMERGENCY OVERRIDE: global lockdown is now "
                                     f"{'ACTIVE' if state else 'DEACTIVATED'}."}

        return {"tele_response": "⚠️ Unknown command. Send /help."}

    def _execute_autonomous_task(self, sender_id: int, payload: dict) -> dict:
        title = str(payload.get("task_name", "Generic Task"))[:200]
        task = self.tasks.create(title, payload, int(payload.get("priority", 50)), sender_id)
        description = payload.get("description") or title
        vote = self.router.vote(f"{title}\n{description}", partial_failure_tolerant=self.partial_failure_tolerant,
                                simulate_offline=self.config.simulate_offline_consensus)
        tally = "\n".join(f"  {v['node']}: {v['vote']}" for v in vote["votes"])
        if not vote["passed"]:
            task.status = "REJECTED"
            self.ledger.append("task_rejected", {"task_id": task.id, "title": title, "approvals": vote["approvals"]})
            return {"tele_response": f"❌ NO CONSENSUS ({vote['approvals']}/{vote['responded']} approve, "
                                     f"{vote['total']} nodes)\n{tally}", "vote": vote}
        block = self.ledger.append("task_approved", {"task_id": task.id, "title": title, "payload": payload,
                                                     "approvals": vote["approvals"], "simulated": vote["simulated"]})
        task.ledger_hash = block["hash"]
        task.status = "APPROVED"
        if payload.get("feature"):
            self.tasks.enqueue(task)
            dispatch = f"queued (runs feature '{payload['feature']}')"
        else:
            task.status = "DONE"
            dispatch = "recorded (no 'feature' attached, nothing to execute)"
        self._fire_triggers("task:approved")
        sim = " [SIMULATED OFFLINE VOTE]" if vote["simulated"] else ""
        return {"tele_response": f"✅ CONSENSUS ACHIEVED{sim}\nTask: {title} (id {task.id})\n{tally}\n"
                                 f"Ledger block: {block['hash'][:16]}\nDispatch: {dispatch}",
                "task_id": task.id, "vote": vote}
