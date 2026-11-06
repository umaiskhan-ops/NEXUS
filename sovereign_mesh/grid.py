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

from .brain_matrix import DecentralizedBrainMatrix
from .continuous_learning import ContinuousSelfImprovementManager
from .config import GridConfig
from .features import Block, FeatureInputError, Kind, build_registry
from .hub_spoke import LightweightWorkerNode, MasterHubCoordinator
from .ledger import HashChainLedger
from .p2p_market import P2PMarketplace
from .supercomputer import SupercomputerEngine
from .models import (BackendUnavailable, DistillationCache, LLMBackend, ModelNode, ModelRouter,
                     OllamaBackend, OpenAICompatibleBackend)
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

        ledger_hmac_key = (
            os.environ.get("LEDGER_HMAC_KEY")
            or config.master_passphrase_hash
            or config.peer_shared_secret
            or config.dashboard_token
        )
        self.ledger = HashChainLedger(self.data_dir / "ledger.jsonl", hmac_key=ledger_hmac_key)
        self.memory = MemoryStore(self.data_dir / "memory.json")
        self.snapshots = SnapshotManager()
        self.budget = TokenBudget(config.token_budget)
        self.tasks = TaskRegistry()
        self.scheduler = Scheduler()
        self.approvals = ApprovalQueue()
        self.triggers = TriggerEngine()
        self.hub = MasterHubCoordinator(self.ledger, grid=self, state_path=self.data_dir / "hub_workers.json")
        self.p2p = P2PMarketplace(self.hub, self.ledger, storage_path=self.data_dir / "p2p_market.json",
                                  owner_id=self.owner_tg_id, notifier=self._notify)
        self.supercomputer = SupercomputerEngine(self.hub, self.ledger,
                                                 storage_path=self.data_dir / "supercomputers.json")
        from .token_sink import TokenSinkManager
        self.token_sink = TokenSinkManager(self.hub, self.ledger, storage_path=self.data_dir / "token_sink.json")

        nodes = [ModelNode(m["name"], m["role"], m["model"]) for m in config.mesh]
        if backend is None:
            if config.llm_api_key:
                backend = OpenAICompatibleBackend(config.llm_base_url or "https://openrouter.ai/api/v1", config.llm_api_key)
            else:
                backend = OllamaBackend(config.ollama_url)
        distillation_cache = DistillationCache(storage_path=self.data_dir / "distillation_cache.json", ledger=self.ledger)
        self.brain_matrix = DecentralizedBrainMatrix(
            distillation_cache=distillation_cache,
            hub=self.hub,
            ledger=self.ledger,
            storage_path=self.data_dir / "brain_matrix.json",
        )
        self.router = ModelRouter(
            nodes,
            backend,
            self.budget,
            config.llm_timeout_s,
            distillation_cache=distillation_cache,
            brain_matrix=self.brain_matrix,
        )
        self.registry = build_registry()
        self.adapters: Dict[str, Callable[[Any, dict], dict]] = {}
        self.continuous_learning = ContinuousSelfImprovementManager(
            self.data_dir,
            ledger=self.ledger,
            router=self.router,
        )

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
        from .ledger import interprocess_file_lock
        path = self.data_dir / "node_id"
        with interprocess_file_lock(path):
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
            payload_dict = task.payload if isinstance(task.payload, dict) else {}
            feature = payload_dict.get("feature")
            if feature:
                raw_fp = payload_dict.get("feature_payload")
                fp = dict(raw_fp) if isinstance(raw_fp, dict) else {}
                res = self.run_feature(task.created_by, feature, fp,
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

    def node_slashing_authority(self, worker_id: str, reason: str = "Malicious activity flagged by Node Slashing Authority") -> dict:
        """Invokes node slashing authority to burn 100% of rogue worker credits and blacklist on ledger."""
        if not getattr(self, "hub", None):
            return {"status": "ERROR", "error": "hub coordinator not available"}
        return self.hub.slash_worker(worker_id, reason)

    def buy_lottery_ticket(self, worker_id: str, count: int = 1) -> dict:
        if not getattr(self, "token_sink", None):
            return {"ok": False, "error": "token_sink not available"}
        return self.token_sink.buy_lottery_ticket(worker_id, count=count)

    def draw_lottery(self, force: bool = False) -> dict:
        if not getattr(self, "token_sink", None):
            return {"ok": False, "error": "token_sink not available"}
        return self.token_sink.draw_lottery_winner(force=force)

    def stake_credits(self, worker_id: str, amount: int) -> dict:
        if not getattr(self, "token_sink", None):
            return {"ok": False, "error": "token_sink not available"}
        return self.token_sink.stake_credits(worker_id, amount)

    def unstake_credits(self, worker_id: str, amount: int) -> dict:
        if not getattr(self, "token_sink", None):
            return {"ok": False, "error": "token_sink not available"}
        return self.token_sink.unstake_credits(worker_id, amount)

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
        ledger_hmac_key = (
            os.environ.get("LEDGER_HMAC_KEY")
            or config.master_passphrase_hash
            or config.peer_shared_secret
            or config.dashboard_token
        )
        self.ledger = HashChainLedger(self.data_dir / "ledger.jsonl", hmac_key=ledger_hmac_key)
        self.memory = MemoryStore(self.data_dir / "memory.json")
        for sub in (
            getattr(self, "hub", None),
            getattr(self, "p2p", None),
            getattr(self, "supercomputer", None),
            getattr(self, "token_sink", None),
            getattr(self, "brain_matrix", None),
            getattr(getattr(self, "router", None), "distillation_cache", None),
        ):
            if sub is not None and hasattr(sub, "ledger"):
                sub.ledger = self.ledger
        self.ledger.append("disaster_recovery_restore", {"backup": name})
        return {"backup": name, "ledger_blocks": len(self.ledger)}

    def peer_signature(self, timestamp: str, path: str = "", nonce: str = "") -> str:
        msg = timestamp if not path else (f"{timestamp}:{path}:{nonce}" if nonce else f"{timestamp}:{path}")
        return hmac.new(self.config.peer_shared_secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()

    def peer_status(self, timeout: float = 3.0) -> List[dict]:
        out = []
        for peer in self.config.peers:
            ts = str(int(time.time()))
            nonce = secrets.token_hex(8)
            path = "/p2p/head"
            req = urllib.request.Request(
                peer["url"].rstrip("/") + path,
                headers={
                    "X-Peer-Timestamp": ts,
                    "X-Peer-Nonce": nonce,
                    "X-Peer-Signature": self.peer_signature(ts, path=path, nonce=nonce),
                },
            )
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
        if sender_id and sender_id != self.owner_tg_id:
            # N9 Fix: Non-owner users are strictly isolated to their own session namespace
            sub_sess = str(payload.get("session") or "").strip()
            if not sub_sess or not sub_sess.startswith(f"user_{sender_id}"):
                payload["session"] = f"user_{sender_id}" if not sub_sess else f"user_{sender_id}:{sub_sess}"
        elif "session" not in payload or not payload.get("session"):
            payload["session"] = "default"
        entry = {"ts": time.time(), "sender": sender_id, "feature": key, "via": via}

        def finish(result: dict) -> dict:
            entry["status"] = result.get("status")
            self._record(entry, log)
            return result

        if key == "node_slashing_authority":
            if self.system_lockdown:
                return finish({"status": "DENIED", "error": "system lockdown active"})
            if self.frozen:
                return finish({"status": "DENIED", "error": "state is frozen (state_snapshot_freeze)"})
            if not self.access.allows(sender_id, Role.OWNER):
                return finish({"status": "DENIED", "error": "node_slashing_authority requires OWNER role"})
            target_wid = payload.get("worker_id") or payload.get("target_worker_id") or ""
            reason = payload.get("reason", "Malicious activity flagged by Node Slashing Authority")
            res = self.hub.slash_worker(target_wid, reason) if getattr(self, "hub", None) else {"status": "ERROR"}
            return finish({"status": "SLASHED" if res.get("status") == "SLASHED" else "OK", **res})

        if key in {"credit_lottery_pool", "lottery_pool", "gamified_credit_lottery"}:
            if self.system_lockdown:
                return finish({"status": "DENIED", "error": "system lockdown active"})
            if not getattr(self, "token_sink", None):
                return finish({"status": "ERROR", "error": "token_sink not initialized"})
            action = payload.get("action", "buy_ticket")
            target_wid = payload.get("worker_id") or payload.get("account_key") or str(sender_id)
            if action == "status":
                res = self.token_sink.get_lottery_status()
                return finish({"status": "OK", **res})
            if self.frozen:
                return finish({"status": "DENIED", "error": "state is frozen (state_snapshot_freeze)"})
            if action == "draw":
                if not self.access.allows(sender_id, Role.OWNER):
                    return finish({"status": "DENIED", "error": "manual lottery draw requires OWNER role"})
                res = self.token_sink.draw_lottery_winner(force=True)
                return finish({"status": "OK", **res})
            try:
                count = int(payload.get("tickets") or payload.get("count", 1) or 1)
            except (ValueError, TypeError):
                return finish({"status": "ERROR", "error": "invalid ticket count"})
            res = self.token_sink.buy_lottery_ticket(target_wid, count=count)
            return finish({"status": "OK" if res.get("ok") else "ERROR", **res})

        if key in {"staking_rewards_vault", "credit_staking_vault", "staking_pool", "credit_staking"}:
            if self.system_lockdown:
                return finish({"status": "DENIED", "error": "system lockdown active"})
            if not getattr(self, "token_sink", None):
                return finish({"status": "ERROR", "error": "token_sink not initialized"})
            action = payload.get("action", "stake")
            target_wid = payload.get("worker_id") or payload.get("account_key") or str(sender_id)
            if action == "status":
                res = self.token_sink.get_staking_status(target_wid)
                return finish({"status": "OK", **res})
            if self.frozen:
                return finish({"status": "DENIED", "error": "state is frozen (state_snapshot_freeze)"})
            try:
                amount = int(payload.get("amount", 50) or 50)
            except (ValueError, TypeError):
                return finish({"status": "ERROR", "error": "invalid staking amount"})
            if action == "unstake":
                res = self.token_sink.unstake_credits(target_wid, amount)
            else:
                res = self.token_sink.stake_credits(target_wid, amount)
            return finish({"status": "OK" if res.get("ok") else "ERROR", **res})

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
        # 2b. Tier access check (Model 2: VIP Feature Access)
        if not approved and sender_id != self.owner_tg_id:
            caller_worker_id = payload.get("as_worker") or payload.get("worker_id")
            caller_credits = 0
            if caller_worker_id and self.hub:
                rec = self.hub.get_worker(caller_worker_id)
                if rec and rec.status == "ACTIVE":
                    caller_credits = rec.credits
            ok_tier, reason = self.registry.check_tier_access(feature.key, caller_credits, is_owner=False)
            if not ok_tier:
                return finish({"status": "TIER_LOCKED", "tier_required": feature.tier.value,
                               "credits": caller_credits, "error": reason})
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
    HELP = ("Commands:\n/status_grid\n/features [block]\n/tiers\n/my_tier [worker_id]\n"
            "/run <feature_key> <text | json>\n"
            "/execute_autonomous_task <name> [| json]\n/tasks\n/models\n"
            "/add_model <name> <role> <model_tag>\n/add_models_bulk [count]\n/remove_model <name>\n"
            "/workers\n/register_worker <id> [url]\n/dispatch_worker <id> <feature> <payload>\n"
            "/balance <worker_id>\n/add_credits <worker_id> <amount> [reason]\n"
            "/spend_credits <worker_id> <amount> [reason]\n"
            "/transfer_credits <from> <to> <amount>\n/barter_task <worker_id> <feature> <payload>\n"
            "/set_payout <worker_id> <address>\n/deposit_revenue <client> <amount> [job_id]\n"
            "/settle_revenue [split_ratio]\n/payout_stats\n"
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
            shown_nodes = self.router.nodes[:15]
            nodes = "\n".join(f"  • {n.name} [{n.role}] {n.model}: {n.status}" for n in shown_nodes)
            if len(self.router.nodes) > 15:
                nodes += f"\n  ... and {len(self.router.nodes) - 15} more active open-source model nodes."
            kinds = self.registry.kind_counts()
            active_workers = len([w for w in self.hub.list_workers() if w.get("status") == "ACTIVE"]) if self.hub else 0
            return {"tele_response": (
                f"📊 SOVEREIGN MESH OVERVIEW\nNode: {self.node_id}\n"
                f"Active Edge Workers: {active_workers} nodes online (/workers to view list)\n"
                f"Model nodes ({len(self.router.nodes)} total):\n{nodes}\n"
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

        if intent == "/tiers":
            counts = self.registry.tier_counts()
            resp = (
                f"🏷️ SYSTEM ACCESS TIERS (130 Features Total):\n"
                f"1. COMMUNITY (Free / Basic, 0 credits): {counts.get('COMMUNITY', 0)} features\n"
                f"2. PRO (Active Contributor, 50+ credits): {counts.get('PRO', 0)} features\n"
                f"   (Includes code generation, static analysis, trend forecasting, refactoring)\n"
                f"3. SOVEREIGN_VIP (VIP Sovereign, 200+ credits or Owner): {counts.get('SOVEREIGN_VIP', 0)} features\n"
                f"   (Includes Monte Carlo simulator, multi-agent debate, consensus, hardware actuators)\n\n"
                f"Contribute compute by running an edge worker node to earn credits and unlock higher tiers!"
            )
            return {"tele_response": resp, "tier_counts": counts}

        if intent == "/run":
            key = payload.pop("feature", "")
            res = self.run_feature(sender_id, key, payload, via="telegram", passphrase=master_key_verification)
            return {"tele_response": f"[{key}] {res.get('status')}\n" +
                                     json.dumps(res, indent=1, default=str)[:3500], "result": res}

        if intent == "/execute_autonomous_task":
            if role < Role.OPERATOR:
                return {"tele_response": "❌ Operator role required."}
            return self._execute_autonomous_task(sender_id, payload)

        if intent in {"/vote", "/consensus", "/verify_task"}:
            prop = payload.get("proposal") or payload.get("text") or "Verify autonomous network safety"
            vote = self.router.vote(prop, partial_failure_tolerant=self.partial_failure_tolerant,
                                    simulate_offline=self.config.simulate_offline_consensus)
            block = self.ledger.append("multi_model_vote", {
                "proposal": prop[:200],
                "passed": vote["passed"],
                "approvals": vote["approvals"],
                "total": vote["total"],
                "simulated": vote.get("simulated", False),
            })
            tally_lines = []
            for v in vote["votes"]:
                emoji = "✅" if v["vote"] == "APPROVE" else ("❌" if v["vote"] == "REJECT" else "⚪")
                tally_lines.append(f"  {emoji} {v['node']}: {v['vote']} ({v.get('reason', '')[:120]})")
            tally_str = "\n".join(tally_lines)
            status_emoji = "✅ CONSENSUS PASSED" if vote["passed"] else "❌ CONSENSUS REJECTED"
            sim_tag = " [OFFLINE SIMULATION]" if vote.get("simulated") else ""
            resp = (
                f"🗳️ MULTI-MODEL VALIDATOR CONSENSUS BOARD{sim_tag}:\n"
                f"• Proposal: \"{prop[:160]}\"\n"
                f"• Verdict: {status_emoji} ({vote['approvals']}/{vote['responded']} Approvals, {vote['total']} Nodes)\n"
                f"• Supermajority Requirement: >= 66.7% (2/3 Quorum)\n\n"
                f"🤖 Network Model Votes:\n{tally_str}\n\n"
                f"🧾 Ledger Block: {block['hash'][:16]}"
            )
            return {"tele_response": resp, "vote": vote, "ledger_block": block["hash"][:16]}

        if intent in {"/debate", "/roundtable"}:
            question = payload.get("question") or payload.get("text") or "Decentralized neural architecture safety"
            rounds = int(payload.get("rounds", 2) or 2)
            deb = self.router.debate(question, rounds=rounds, simulate_offline=self.config.simulate_offline_consensus)
            round_lines = []
            for r in deb.get("rounds", []):
                round_lines.append(f"\n--- Round {r['round']} (Expert Positions) ---")
                for pos in r.get("positions", []):
                    txt = (pos.get("text") or pos.get("error") or "")[:250]
                    round_lines.append(f"• [{pos['node']}]: {txt}")
            rounds_str = "\n".join(round_lines)
            resp = (
                f"🗣️ MULTI-MODEL ROUNDTABLE DEBATE & VERIFICATION:\n"
                f"• Topic: \"{question[:160]}\"\n"
                f"• Active Panelists: {len(self.router.nodes)} Model Nodes\n"
                f"{rounds_str}\n\n"
                f"🎯 Consensus Synthesis & Moderator Verdict:\n"
                f"{deb.get('synthesis', '')}"
            )
            return {"tele_response": resp, "debate": deb}

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
            shown = self.router.nodes[:25]
            active = "\n".join(f"  • {n.name} [{n.role}] -> {n.model} ({n.status})" for n in shown)
            if len(self.router.nodes) > 25:
                active += f"\n  ... and {len(self.router.nodes) - 25} more open-source models active in mesh."
            available = self.router.available_models()
            avail_str = ", ".join(available) if available else "(backend idle / none listed)"
            return {"tele_response": f"🤖 ACTIVE SWARM NODES ({len(self.router.nodes)}):\n{active}\n\n"
                                     f"📦 DISCOVERED IN BACKEND:\n{avail_str}\n\n"
                                     f"Use /add_model <name> <role> <model_tag> or /add_models_bulk 300 to register models."}

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

        if intent in {"/add_models_bulk", "/add_300_models"}:
            if role is not Role.OWNER:
                return {"tele_response": "❌ Owner role required to bulk-add models."}
            count = int(payload.get("count", 300) or 300)
            res = self.router.add_open_source_models_bulk(count)
            self.ledger.append("models_bulk_added", {
                "requested": count,
                "added_count": res["added_count"],
                "total_mesh_nodes": res["total_mesh_nodes"],
            })
            sample_str = "\n".join(f"  • {name}" for name in res["sample_nodes"])
            return {
                "tele_response": (
                    f"✅ BULK OPEN-SOURCE MODELS REGISTERED!\n"
                    f"Added Now: {res['added_count']} (Requested: {count})\n"
                    f"Total Active Models in Mesh: {res['total_mesh_nodes']}\n\n"
                    f"Sample Nodes:\n{sample_str}"
                ),
                "bulk_result": res,
            }

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
                return {"tele_response": "❌ Usage: /register_worker <worker_id> [url] [referred_by]"}
            try:
                rec = self.hub.register_worker(
                    wid,
                    payload.get("url", "local"),
                    hardware_uuid=payload.get("hardware_uuid", ""),
                    hardware_spec=payload.get("hardware_spec", ""),
                    referred_by=payload.get("referred_by", ""),
                )
                return {"tele_response": f"✅ Worker registered: {rec.worker_id} (Initial stake: {rec.credits} credits | Referral Code: {rec.referral_code})",
                        "worker_key": rec.key, "referral_code": rec.referral_code}
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

        if intent == "/my_tier":
            wid = payload.get("worker_id") or payload.get("text")
            if not wid:
                if role is Role.OWNER:
                    return {"tele_response": "👑 Owner role detected: Unconditional SOVEREIGN_VIP access to all 130 features."}
                return {"tele_response": "Usage: /my_tier <worker_id>"}
            try:
                bal = self.hub.get_balance(wid)
                return {"tele_response": f"👤 Worker {wid} [{bal['tier']} Tier]\n"
                                         f"Balance: {bal['credits']} UMAIS (Credits: {bal['credits']}) | Status: {bal['status']}\n"
                                         f"Tasks Completed: {bal['tasks_completed']} | Verified: {bal['tasks_verified']}\n"
                                         f"Pending Payout: ${bal['pending_payout_usd']:.2f} (Total: ${bal['total_payout_earned_usd']:.2f})"}
            except KeyError:
                return {"tele_response": f"❌ Unknown worker: {wid}"}

        if intent == "/balance":
            wid = payload.get("worker_id") or payload.get("text")
            if not wid:
                return {"tele_response": "❌ Usage: /balance <worker_id>"}
            try:
                b = self.hub.get_balance(wid)
                return {"tele_response": f"💳 Worker {wid} Balance (1 Credit = 1 UMAIS):\n"
                                         f"Balance: {b['credits']} UMAIS (Credits: {b['credits']}) [{b['tier']} Tier]\n"
                                         f"Pending Payout: ${b['pending_payout_usd']:.2f}\n"
                                         f"Total Payout Earned: ${b['total_payout_earned_usd']:.2f}\n"
                                         f"Payout Address: {b['payout_address']}",
                        "balance": b}
            except KeyError:
                return {"tele_response": f"❌ Unknown worker: {wid}"}

        if intent in {"/add_credits", "/grant_credits"}:
            if role is not Role.OWNER:
                return {"tele_response": "❌ Owner role required to grant credits."}
            wid = payload.get("worker_id", "")
            amount = int(payload.get("amount", 0) or 0)
            reason = payload.get("reason", "owner_grant")
            if not wid or amount <= 0:
                return {"tele_response": "❌ Usage: /add_credits <worker_id_or_key> <amount> [reason]"}
            try:
                res = self.hub.grant_credits(wid, amount, reason)
                return {
                    "tele_response": (
                        f"💰 CREDITS GRANTED SUCCESSFULLY! (1 Credit = 1 UMAIS)\n"
                        f"Worker: {res['worker_id']}\n"
                        f"Added: +{res['added_credits']} UMAIS / credits ({res['reason']})\n"
                        f"Previous Balance: {res['previous_credits']} UMAIS -> New Balance: {res['new_credits']} UMAIS [{res['tier']} Tier]"
                    ),
                    "grant_result": res,
                }
            except (KeyError, PermissionError, ValueError) as exc:
                return {"tele_response": f"❌ {exc}"}

        if intent == "/spend_credits":
            wid = payload.get("worker_id", "")
            amount = int(payload.get("amount", 0) or 0)
            reason = payload.get("reason", "manual_spend")
            if not wid or amount <= 0:
                return {"tele_response": "❌ Usage: /spend_credits <worker_id> <amount> [reason]"}
            try:
                res = self.hub.spend_credits(wid, amount, reason)
                if res.get("status") == "INSUFFICIENT_CREDITS":
                    return {"tele_response": f"❌ {res.get('error')}"}
                return {"tele_response": f"💸 Spent {amount} credits from {wid}. Remaining: {res['remaining_credits']}"}
            except (KeyError, PermissionError, ValueError) as exc:
                return {"tele_response": f"❌ {exc}"}

        if intent == "/transfer_credits":
            from_w = payload.get("from_worker", "")
            to_w = payload.get("to_worker", "")
            amount = int(payload.get("amount", 0) or 0)
            if not from_w or not to_w or amount <= 0:
                return {"tele_response": "❌ Usage: /transfer_credits <from_worker> <to_worker> <amount>"}
            try:
                res = self.hub.transfer_credits(from_w, to_w, amount)
                if res.get("status") == "INSUFFICIENT_CREDITS":
                    return {"tele_response": f"❌ Insufficient credits in {from_w} (balance: {res.get('balance')})"}
                return {"tele_response": f"🤝 Transferred {amount} credits: {from_w} ({res['from_balance']}) ➡️ {to_w} ({res['to_balance']})"}
            except (KeyError, PermissionError, ValueError) as exc:
                return {"tele_response": f"❌ {exc}"}

        if intent == "/barter_task":
            # Model 1: Deducts 20 compute credits to dispatch a task on the mesh
            wid = payload.get("worker_id", "")
            fkey = payload.get("feature", "")
            task_payload = payload.get("task_payload", {})
            if not wid or not fkey:
                return {"tele_response": "❌ Usage: /barter_task <worker_id> <feature_key> <text_or_json>"}
            try:
                spent = self.hub.spend_credits(wid, 20, reason=f"barter_compute:{fkey}")
                if spent.get("status") == "INSUFFICIENT_CREDITS":
                    return {"tele_response": f"❌ Barter rejected: {spent.get('error')}"}
                res = self.run_feature(sender_id, fkey, task_payload, via="barter_compute")
                return {"tele_response": f"⚡ BARTER COMPUTE EXECUTED (20 credits deducted, {spent['remaining_credits']} remaining):\n"
                                         f"{json.dumps(res, indent=1, default=str)[:3500]}",
                        "result": res, "barter": spent}
            except (KeyError, PermissionError, ValueError) as exc:
                return {"tele_response": f"❌ {exc}"}

        if intent == "/set_payout":
            wid = payload.get("worker_id", "")
            addr = payload.get("address") or payload.get("text", "")
            if not wid or not addr:
                return {"tele_response": "❌ Usage: /set_payout <worker_id> <address_or_iban_or_paypal>"}
            try:
                res = self.hub.set_payout_address(wid, addr)
                return {"tele_response": f"🏦 Payout address for {wid} set to: {res['payout_address']}"}
            except (KeyError, ValueError) as exc:
                return {"tele_response": f"❌ {exc}"}

        if intent == "/deposit_revenue":
            if role is not Role.OWNER:
                return {"tele_response": "❌ Owner role required to record commercial revenue."}
            client = payload.get("client") or payload.get("client_name", "EnterpriseClient")
            amt = float(payload.get("amount") or payload.get("amount_usd", 0.0) or 0.0)
            job_id = payload.get("job_id", "")
            if amt <= 0:
                return {"tele_response": "❌ Usage: /deposit_revenue <client> <amount_usd> [job_id]"}
            try:
                res = self.hub.deposit_commercial_revenue(amt, client, job_id)
                return {"tele_response": f"💵 Commercial deposit recorded: ${amt:.2f} from {client}.\n"
                                         f"Total Revenue Pool: ${res['commercial_revenue_pool_usd']:.2f}"}
            except ValueError as exc:
                return {"tele_response": f"❌ {exc}"}

        if intent == "/settle_revenue":
            if role is not Role.OWNER:
                return {"tele_response": "❌ Owner role required to settle revenue epoch."}
            ratio = float(payload.get("split_ratio", 0.70) or 0.70)
            res = self.hub.settle_epoch_revenue_split(ratio)
            if res.get("status") == "NO_REVENUE":
                return {"tele_response": "ℹ️ Commercial revenue pool is empty ($0.00)."}
            lines = [f"  • {d['worker_id']}: ${d['payout_usd']:.2f} (Epoch tasks: {d['epoch_tasks']}, Pending: ${d['pending_payout_usd']:.2f})"
                     for d in res.get("distributions", [])]
            dist_str = "\n".join(lines) if lines else "  (No active worker completed verified tasks this epoch)"
            return {"tele_response": (
                f"🎉 REVENUE EPOCH #{res['epoch']} SETTLED ({res['split_ratio']}):\n"
                f"Total Pool: ${res['total_revenue_usd']:.2f}\n"
                f"Workers Share (70%): ${res['workers_pool_usd']:.2f}\n"
                f"Treasury Retained (30%): ${res['treasury_pool_usd']:.2f}\n"
                f"Distributions:\n{dist_str}"),
                "settlement": res}

        if intent == "/payout_stats":
            stats = self.hub.payout_stats()
            workers = stats.get("workers", [])
            lines = [f"  • {w['worker_id']}: Pending ${w['pending_payout_usd']:.2f} | Total ${w['total_payout_earned_usd']:.2f} | Acc: {w['payout_address']}"
                     for w in workers]
            return {"tele_response": (
                f"📊 COMMERCIAL REVENUE & PAYOUT STATS (Epoch {stats['current_epoch']}):\n"
                f"Current Commercial Pool: ${stats['commercial_revenue_pool_usd']:.2f}\n"
                f"Treasury Balance: ${stats['treasury_balance_usd']:.2f}\n"
                f"Registered Workers ({len(workers)}):\n" + "\n".join(lines)),
                "stats": stats}

        if intent in {"/top_miners", "/leaderboard"}:
            limit = int(payload.get("limit", 10) or 10)
            lb = self.hub.get_top_miners_leaderboard(limit=limit)
            halving = lb["halving"]
            leaders = lb["leaderboard"]
            lines = [
                f"  {m['badge'] or ('#' + str(m['rank']))} {m['worker_id']} [{m.get('hardware_spec', 'Standard Rig')}] — "
                f"Score: {m['competition_score']} (Tasks: {m['tasks_verified']}, Uptime: {m['uptime_hours']}h, "
                f"Credits: {m['credits']}, Referrals: {m.get('referrals_count', 0)})"
                for m in leaders
            ]
            body_str = "\n".join(lines) if lines else "  (No active miners yet)"
            return {
                "tele_response": (
                    f"🏆 WEEKLY SUNDAY TOP 3 MINERS BUYBACK LEADERBOARD (HARDWARE FLEX):\n"
                    f"⚡ Halving Era: {halving['era']} ({halving['active_workers']} Active Workers)\n"
                    f"⛏️ Idle Mining Rate: {halving['idle_credits_per_hour_standard']} cr/hr (Standard) | "
                    f"Active Task Reward: +{halving['active_task_reward_credits']} cr/task\n"
                    f"💰 Sunday Official Floor Buyback: {lb['sunday_buyback_pool']['official_floor_rate_pkr']} PKR each for Top 3!\n\n"
                    f"Current Rankings:\n{body_str}\n\n"
                    f"👑 Owner Command to Settle Top 3 Buyback: /reward_top_miners [pkr_each] [credits_each]"
                ),
                "leaderboard": lb,
            }

        if intent in {"/referral", "/referrals"}:
            wid = payload.get("worker_id") or payload.get("text", "")
            if not wid:
                return {"tele_response": "👥 Usage: /referral <worker_id_or_key>\nEarn +5% extra bonus credits on all mining & tasks completed by workers who join with your Referral Code!"}
            try:
                bal = self.hub.get_balance(wid)
                return {
                    "tele_response": (
                        f"👥 VIRAL REFERRAL MULTIPLIER (+5% NETWORK EFFECT):\n"
                        f"• Worker: {bal['worker_id']}\n"
                        f"• Your Referral Code: {bal['referral_code']}\n"
                        f"• Referred By: {bal.get('referred_by') or '(Direct Genesis Node)'}\n"
                        f"• Active Referrals Joined: {bal.get('referrals_count', 0)} workers\n"
                        f"• Total +5% Bonus Credits Earned: +{bal.get('referral_bonus_credits', 0)} credits\n\n"
                        f"🚀 Share your Referral Code '{bal['referral_code']}' on X, LinkedIn, or Reddit — whenever your invited workers mine or complete tasks, the protocol automatically mints +5% extra bonus credits to your wallet!"
                    ),
                    "referral": bal,
                }
            except KeyError:
                return {"tele_response": f"❌ Unknown worker: {wid}"}

        if intent in {"/distillation_stats", "/cot_cache"}:
            dstats = self.router.distillation_stats()
            return {
                "tele_response": (
                    f"🧠 CoT KNOWLEDGE DISTILLATION & LOCAL SELF-TRAINING CACHE:\n"
                    f"• Cached Frontier CoT Solutions: {dstats['cached_cot_solutions']}\n"
                    f"• External Frontier API Calls Saved: {dstats['external_api_calls_saved']}\n"
                    f"• Buyer Credits Saved via Local Distillation: {dstats['estimated_credits_saved']} credits"
                ),
                "distillation_stats": dstats,
            }

        if intent in {"/brain_matrix", "/brain"}:
            bstatus = self.brain_matrix.autonomy_era_status()
            shards_lines = [
                f"  • [{s['shard_id']}] {s['base_expert']} — Holders: {s['active_worker_holders']} workers ({s['target_hardware']})"
                for s in bstatus["specialization_shards"]
            ]
            fl = bstatus["freedom_loop_stats"]
            p2p_mem = bstatus["p2p_memory_fusion"]
            surv = p2p_mem["survivability"]
            return {
                "tele_response": (
                    f"🧠 DECENTRALIZED BRAIN MATRIX (THE FREEDOM LOOP):\n"
                    f"⚡ Current Phase: {bstatus['era_name']}\n"
                    f"📉 External API Dependency: {bstatus['effective_api_dependency_pct']}% (Baseline: {bstatus['baseline_api_dependency_pct']}%)\n"
                    f"🚀 Local Brain Autonomy: {bstatus['local_brain_autonomy_pct']}%\n\n"
                    f"1️⃣ Brain Splitting & Specialization Shards:\n" + "\n".join(shards_lines) + "\n\n"
                    f"2️⃣ Self-Play & Synthetic Dataset Generation:\n"
                    f"  • Self-Play Cycles Run: {fl['self_play_cycles_run']}\n"
                    f"  • Verified Synthetic Samples: {fl['synthetic_samples_verified']}\n"
                    f"  • Total Distilled + Synthetic CoT Units: {fl['cached_cot_solutions']}\n"
                    f"  • External API Calls Saved: {fl['external_api_calls_saved']}\n\n"
                    f"3️⃣ P2P Memory Fusion & Shared Weights Ledger:\n"
                    f"  • Replicated Weight Deltas: {p2p_mem['total_weight_deltas']}\n"
                    f"  • Brain Survival Rate: {surv['brain_survival_rate_pct']}% (Immortal P2P Backup: {'YES' if surv['immortal_status'] else 'DEGRADED'})"
                ),
                "brain_matrix": bstatus,
            }

        if intent == "/self_play":
            seed = payload.get("seed_prompt") or payload.get("text") or "Distributed Byzantine fault-tolerant neural consensus and formal verification"
            count = int(payload.get("variations_count", 4) or 4)
            sp = self.brain_matrix.run_self_play_freedom_loop(seed_prompt=seed, variations_count=count)
            return {
                "tele_response": (
                    f"🔄 SELF-PLAY & SYNTHETIC FREEDOM LOOP COMPLETED:\n"
                    f"• Target Brain Shard: {sp['domain_shard']} ({sp['base_expert']})\n"
                    f"• Seed Topic: {sp['seed_topic']}\n"
                    f"• Verified Synthetic Q&A + Contradiction Proofs Added: +{sp['synthetic_verified']}\n"
                    f"• P2P Weight Delta Synced: {sp['p2p_delta']['delta_id']} (Holders: {', '.join(sp['p2p_delta']['holder_worker_ids'])})"
                ),
                "self_play": sp,
            }

        if intent == "/brain_sync":
            shard = payload.get("domain_shard") or payload.get("text") or "CODE_DEBUG_EXEC"
            if shard not in {"MATH_PROOF_LOGIC", "CODE_DEBUG_EXEC", "SECURITY_AUDIT_REDTEAM", "DATA_MEMORY_SYNTHESIS"}:
                shard = "CODE_DEBUG_EXEC"
            delta = self.brain_matrix.sync_p2p_weight_delta(
                domain_shard=shard,
                delta_summary=f"Manual P2P Weight & Memory Fusion Sync for {shard}",
            )
            return {
                "tele_response": (
                    f"🌐 P2P MEMORY FUSION & SHARED WEIGHTS DELTA SYNCED:\n"
                    f"• Delta ID: {delta['delta_id']}\n"
                    f"• Domain Shard: {delta['domain_shard']}\n"
                    f"• SHA-256 Anchor: {delta['sha256_anchor'][:24]}...\n"
                    f"• Replicated Across ({delta['replication_factor']} Nodes): {', '.join(delta['holder_worker_ids'])}"
                ),
                "delta": delta,
            }

        if intent in {"/reward_top_miners", "/buyback_top3"}:
            if role is not Role.OWNER:
                return {"tele_response": "❌ Owner role required to settle Weekly Top 3 Miners Buyback."}
            pkr_each = float(payload.get("reward_pkr_each", 500.0) or 500.0)
            cr_each = int(payload.get("credits_bought_each", 100) or 100)
            res = self.hub.execute_weekly_top3_buyback(reward_pkr_each=pkr_each, credits_bought_each=cr_each)
            if not res.get("ok"):
                return {"tele_response": f"❌ {res.get('error')}"}
            lines = [
                f"  #{w['rank']} {w['worker_id']}: Paid PKR {w['reward_pkr']:.0f} (${w['reward_usd_equivalent']:.2f}) "
                f"| Bought {w['credits_bought_back']} cr (Remaining: {w['remaining_credits']} cr) | Acc: {w['payout_address']}"
                for w in res.get("winners", [])
            ]
            return {
                "tele_response": (
                    f"🎉 WEEKLY TOP 3 MINERS OFFICIAL BUYBACK SETTLED!\n"
                    f"Total Paid: PKR {res['total_pkr_paid']:.0f} | Total Credits Bought Back: {res['total_credits_bought_back']} cr\n"
                    f"Winners:\n" + "\n".join(lines) + f"\nLedger Block: {res['ledger_block']}"
                ),
                "buyback": res,
            }

        if intent in {"/p2p_market", "/market"}:
            orders = self.p2p.list_orders(status="OPEN")
            stats = self.p2p.market_stats()
            if not orders:
                return {"tele_response": (
                    f"🤝 P2P CREDITS MARKETPLACE:\n"
                    f"No active sell offers right now.\n\n"
                    f"💡 To SELL your earned credits for EasyPaisa/JazzCash:\n"
                    f"  /p2p_sell <worker_id> <credits> <price_pkr> <payment_info>\n"
                    f"  Example: /p2p_sell worker-1 50 250 EasyPaisa:03001234567"),
                    "market_stats": stats, "orders": []}
            lines = [
                f"  🏷️ [{o['order_id']}] {o['amount_credits']} Credits for {o['currency']} {o['price_fiat']:.0f} "
                f"({o['price_per_credit']:.1f}/credit) by {o['seller_id']} | Method: {o['payment_method']}"
                for o in orders
            ]
            return {"tele_response": (
                f"🤝 P2P CREDITS MARKETPLACE ({len(orders)} offers open):\n" + "\n".join(lines) + "\n\n"
                f"💡 To BUY credits: /p2p_buy <order_id> <your_worker_id>\n"
                f"💡 To SELL credits: /p2p_sell <worker_id> <amount> <price_pkr> <payment_info>"),
                "orders": orders, "market_stats": stats}

        if intent == "/p2p_sell":
            wid = payload.get("worker_id", "")
            amt = int(payload.get("amount", 0) or 0)
            price = float(payload.get("price", 0.0) or 0.0)
            method = payload.get("payment_method") or payload.get("text", "")
            curr = payload.get("currency", "PKR")
            if not wid or amt <= 0 or price <= 0:
                return {"tele_response": "❌ Usage: /p2p_sell <worker_id> <credits_amount> <price_pkr> <payment_info>\n"
                                         "Example: /p2p_sell worker-1 100 500 EasyPaisa:03001234567"}
            try:
                res = self.p2p.create_sell_order(wid, amt, price, method or "EasyPaisa / JazzCash", currency=curr)
                if not res.get("ok"):
                    return {"tele_response": f"❌ {res.get('error')}"}
                return {"tele_response": (
                    f"✅ SELL OFFER LISTED & ESCROW LOCKED!\n"
                    f"Order ID: {res['order_id']}\n"
                    f"Offering: {amt} Credits for {curr} {price:.2f}\n"
                    f"Escrow: {amt} credits locked from {wid} (Remaining: {res['seller_balance']})\n"
                    f"Buyer can now buy this order via Web Studio or Telegram.")}
            except Exception as exc:
                return {"tele_response": f"❌ {exc}"}

        if intent == "/p2p_buy_order":
            bid = payload.get("buyer_id") or payload.get("worker_id", "")
            amt = int(payload.get("amount", 0) or 0)
            price = float(payload.get("price", 0.0) or 0.0)
            method = payload.get("payment_method") or payload.get("text", "EasyPaisa / JazzCash")
            curr = payload.get("currency", "PKR")
            if not bid or amt <= 0 or price <= 0:
                return {"tele_response": "❌ Usage: /p2p_buy_order <buyer_id> <credits_amount> <offered_price_pkr> [payment_method]\n"
                                         "Example: /p2p_buy_order buyer-1 250 150 EasyPaisa"}
            try:
                res = self.p2p.create_buy_order(bid, amt, price, method, currency=curr)
                if not res.get("ok"):
                    return {"tele_response": f"❌ {res.get('error')}"}
                return {"tele_response": (
                    f"📢 BUY ORDER PUBLISHED ON P2P MARKET!\n"
                    f"Order ID: {res['order_id']}\n"
                    f"Want to Buy: {amt} Credits for {curr} {price:.2f}\n"
                    f"Buyer: {res['buyer_id']} | Preferred Method: {res['payment_method']}\n"
                    f"Any Miner/Seller can now accept your Buy Order via Web Studio or /p2p_sell_to_buyer!")}
            except Exception as exc:
                return {"tele_response": f"❌ {exc}"}

        if intent == "/p2p_sell_to_buyer":
            oid = payload.get("order_id", "")
            sid = payload.get("seller_id", "")
            method = payload.get("payment_method") or payload.get("text", "")
            if not oid or not sid:
                return {"tele_response": "❌ Usage: /p2p_sell_to_buyer <order_id> <seller_id> <your_easypaisa_or_jazzcash>"}
            try:
                res = self.p2p.accept_buy_order(oid, sid, seller_payment_method=method)
                if not res.get("ok"):
                    return {"tele_response": f"❌ {res.get('error')}"}
                return {"tele_response": (
                    f"🔒 BUY ORDER ACCEPTED & CREDITS LOCKED IN ESCROW!\n"
                    f"Order ID: {res['order_id']}\n"
                    f"Seller: {res['seller_id']} ➡️ Buyer: {res['buyer_id']}\n"
                    f"Escrow Locked: {res['amount_credits']} Credits (Remaining Balance: {res['seller_balance']})\n"
                    f"Buyer will now send {res['currency']} {res['price_fiat']:.2f} to {res['payment_method']}.")}
            except Exception as exc:
                return {"tele_response": f"❌ {exc}"}

        if intent == "/p2p_buy":
            oid = payload.get("order_id", "")
            bid = payload.get("buyer_id") or payload.get("buyer_worker_id", "")
            if not oid or not bid:
                return {"tele_response": "❌ Usage: /p2p_buy <order_id> <buyer_worker_id>"}
            try:
                res = self.p2p.initiate_buy(oid, bid)
                if not res.get("ok"):
                    return {"tele_response": f"❌ {res.get('error')}"}
                return {"tele_response": (
                    f"🔒 ORDER RESERVED IN ESCROW!\n"
                    f"Order: {res['order_id']} ({res['amount_credits']} Credits)\n"
                    f"Total Amount to Pay: {res['currency']} {res['price_fiat']:.2f}\n"
                    f"Payment Details: {res['payment_method']}\n\n"
                    f"👉 Once you send money via EasyPaisa/JazzCash, notify the seller with:\n"
                    f"  /p2p_pay {res['order_id']} {bid} <Transaction_ID>")}
            except Exception as exc:
                return {"tele_response": f"❌ {exc}"}

        if intent == "/p2p_pay":
            oid = payload.get("order_id", "")
            bid = payload.get("buyer_id") or payload.get("buyer_worker_id", "")
            ref = payload.get("ref") or payload.get("tid") or payload.get("text", "")
            if not oid or not bid or not ref:
                return {"tele_response": "❌ Usage: /p2p_pay <order_id> <buyer_worker_id> <TID_or_receipt>"}
            try:
                res = self.p2p.submit_payment(oid, bid, ref)
                if not res.get("ok"):
                    return {"tele_response": f"❌ {res.get('error')}"}
                return {"tele_response": f"📨 {res['message']}\nTID: {ref}"}
            except Exception as exc:
                return {"tele_response": f"❌ {exc}"}

        if intent in {"/dispute", "/p2p_dispute"}:
            oid = payload.get("order_id", "")
            cid = payload.get("caller_id") or payload.get("worker_id") or str(sender_id)
            reason = payload.get("reason") or payload.get("text", "Payment / Screenshot Dispute")
            is_owner = (role is Role.OWNER)
            if not oid:
                return {"tele_response": "❌ Usage: /dispute <order_id> <your_worker_id> [reason]"}
            try:
                res = self.p2p.raise_dispute(oid, cid, reason=reason, is_owner=is_owner)
                if not res.get("ok"):
                    return {"tele_response": f"❌ {res.get('error')}"}
                return {
                    "tele_response": (
                        f"🚨 P2P DISPUTE RAISED & ACCOUNTS FROZEN!\n"
                        f"Order: {res['order_id']} (Status: {res['status']})\n"
                        f"Frozen Accounts: {', '.join(res.get('frozen_accounts', []))}\n"
                        f"Reason: {res['reason']}\n"
                        f"📲 Sovereign Owner has been notified on Telegram for arbitration.\n"
                        f"Ledger Block: {res['ledger_block']}"
                    ),
                    "dispute": res,
                }
            except Exception as exc:
                return {"tele_response": f"❌ {exc}"}

        if intent == "/p2p_release":
            oid = payload.get("order_id", "")
            sid = payload.get("seller_id", "")
            is_owner = (role is Role.OWNER)
            if not oid:
                return {"tele_response": "❌ Usage: /p2p_release <order_id> [seller_id]"}
            try:
                res = self.p2p.confirm_and_release(oid, sid or str(sender_id), is_owner=is_owner)
                if not res.get("ok"):
                    return {"tele_response": f"❌ {res.get('error')}"}
                return {"tele_response": (
                    f"🎉 ESCROW RELEASED & TRADE SETTLED!\n"
                    f"Order: {res['order_id']}\n"
                    f"{res['credits_released']} Credits delivered to Buyer '{res['buyer_id']}'!\n"
                    f"Buyer New Balance: {res['buyer_new_balance']} credits.\n"
                    f"Ledger Block: {res['ledger_block']}")}
            except Exception as exc:
                return {"tele_response": f"❌ {exc}"}

        if intent == "/p2p_cancel":
            oid = payload.get("order_id", "")
            sid = payload.get("seller_id", "")
            is_owner = (role is Role.OWNER)
            if not oid:
                return {"tele_response": "❌ Usage: /p2p_cancel <order_id> [seller_id]"}
            try:
                res = self.p2p.cancel_order(oid, sid or str(sender_id), is_owner=is_owner)
                if not res.get("ok"):
                    return {"tele_response": f"❌ {res.get('error')}"}
                return {"tele_response": f"↩️ Order {res['order_id']} cancelled. {res['refunded_credits']} credits refunded to {res['seller_id']}."}
            except Exception as exc:
                return {"tele_response": f"❌ {exc}"}

        if intent in {"/rent_server", "/rent_cluster"}:
            wid = payload.get("worker_id") or payload.get("account_key", "")
            cores = int(payload.get("cores", 8) or 8)
            ram = int(payload.get("ram_gb") or payload.get("ram", 32) or 32)
            duration = int(payload.get("duration", 1) or 1)
            tier = payload.get("tier_name") or f"Cluster-{cores}C-{ram}GB"
            if not wid:
                return {"tele_response": "❌ Usage: /rent_server <account_key> <cores> <ram_gb> [duration_hours]"}
            try:
                res = self.supercomputer.provision_server(wid, tier, cores, ram, duration)
                if not res.get("ok"):
                    return {"tele_response": f"❌ {res.get('error')}"}
                inst = res["instance"]
                return {"tele_response": (
                    f"🚀 SUPERCOMPUTER CLUSTER PROVISIONED!\n"
                    f"Instance ID: {inst['instance_id']}\n"
                    f"Tier: {inst['tier_name']}\n"
                    f"Cores: {inst['allocated_cores']} vCPUs | RAM: {inst['allocated_ram_gb']} GB\n"
                    f"Pooled Edge Workers: {inst['nodes_count']} nodes\n"
                    f"Virtual Endpoint: {inst['endpoint']}\n"
                    f"Duration: {inst['duration_hours']} hour(s) (Cost: {res['credits_spent']} credits)\n"
                    f"Remaining Balance: {res['remaining_credits']} credits\n"
                    f"Ledger Hash: {res['ledger_block']}"),
                    "instance": inst}
            except Exception as exc:
                return {"tele_response": f"❌ {exc}"}

        if intent in {"/my_servers", "/supercomputers"}:
            wid = payload.get("worker_id") or payload.get("account_key", "")
            servers = self.supercomputer.list_instances(wid or None)
            if not servers:
                return {"tele_response": "ℹ️ No supercomputer clusters active. Rent one with /rent_server!"}
            lines = [
                f"  🖥️ [{s['instance_id']}] {s['tier_name']} ({s['allocated_cores']} cores, {s['allocated_ram_gb']}GB) - "
                f"{s['status']} ({s['nodes_count']} workers pooled, {s['remaining_seconds']}s left)"
                for s in servers
            ]
            return {"tele_response": f"🚀 CLUSTERED SUPERCOMPUTERS ({len(servers)}):\n" + "\n".join(lines),
                    "servers": servers}

        if intent == "/run_server_job":
            iid = payload.get("instance_id", "")
            wid = payload.get("worker_id") or payload.get("account_key", "")
            name = payload.get("job_name", "Telegram Parallel Task")
            if not iid:
                return {"tele_response": "❌ Usage: /run_server_job <instance_id> <account_key> [job_name]"}
            try:
                res = self.supercomputer.dispatch_job(iid, wid, name, "")
                if not res.get("ok"):
                    return {"tele_response": f"❌ {res.get('error')}"}
                job = res["job"]
                return {"tele_response": (
                    f"⚡ CLUSTER JOB EXECUTED!\n"
                    f"Job ID: {job['job_id']}\n"
                    f"Instance: {iid}\n"
                    f"Distributed Across: {job['nodes_utilized']} edge nodes ({job['cores_active']} cores)\n"
                    f"Execution Time: {job['elapsed_ms']} ms\n"
                    f"Telemetry: {job['summary']}"),
                    "job": job}
            except Exception as exc:
                return {"tele_response": f"❌ {exc}"}

        if intent == "/pause_server":
            iid = payload.get("instance_id", "")
            wid = payload.get("worker_id") or payload.get("account_key", "")
            if not iid:
                return {"tele_response": "❌ Usage: /pause_server <instance_id>"}
            res = self.supercomputer.pause_server(iid, wid)
            if not res.get("ok"):
                return {"tele_response": f"❌ {res.get('error')}"}
            return {"tele_response": f"⏸️ {res['message']}", "instance": res.get("instance")}

        if intent == "/resume_server":
            iid = payload.get("instance_id", "")
            wid = payload.get("worker_id") or payload.get("account_key", "")
            if not iid:
                return {"tele_response": "❌ Usage: /resume_server <instance_id>"}
            res = self.supercomputer.resume_server(iid, wid)
            if not res.get("ok"):
                return {"tele_response": f"❌ {res.get('error')}"}
            return {"tele_response": f"▶️ {res['message']}", "instance": res.get("instance")}

        if intent in {"/stop_server", "/terminate_server"}:
            iid = payload.get("instance_id", "")
            wid = payload.get("worker_id") or payload.get("account_key", "")
            if not iid:
                return {"tele_response": "❌ Usage: /stop_server <instance_id>"}
            try:
                res = self.supercomputer.terminate_server(iid, wid)
                if not res.get("ok"):
                    return {"tele_response": f"❌ {res.get('error')}"}
                return {"tele_response": f"🛑 {res['message']}"}
            except Exception as exc:
                return {"tele_response": f"❌ {exc}"}

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


# Alias for clean programmatic and architectural naming
SovereignGrid = UltimateAgiSovereignGrid

