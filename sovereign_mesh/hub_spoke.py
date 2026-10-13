"""Hybrid Hub-and-Spoke: the Master Hub keeps all governance; edge Workers only execute signed tasks.

Security model (read this before relying on slashing):
  * Every worker gets its OWN random key at registration (no shared secret). A valid proof is therefore
    attributable: only the Hub and that one worker know the key.
  * An INVALID proof is rejected but never slashed, because it cannot be attributed (anyone can send garbage
    in someone else's name; slashing on that would let attackers burn honest workers' credits).
  * Slashing happens only on PROVABLE misbehaviour: a correctly-signed result that disagrees with the Hub's own
    re-execution (spot-check) of a deterministic feature.
  * Non-deterministic (LLM) results cannot be verified by recomputation; they are accepted and marked
    `verified: false`. Do not treat them as proven correct.
  * Credits are an internal accounting number, not money or a token.
"""
from __future__ import annotations

import dataclasses
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .features import FeatureRegistry, build_registry
from .ledger import HashChainLedger
from .security import sanitize_payload

# Governance, control, hardware and anything that can fan out into other features stays on the Hub.
HUB_ONLY_FEATURES: Set[str] = {
    "mission_control", "veto_power", "approval_gates", "full_transparency_ledger", "emergency_override",
    "shutdown_authority", "access_control", "mission_change_rollbacks", "simulation_rollback",
    "grid_state_rollback", "final_say_protocol", "kill_switch_protocol", "token_budget_controller",
    "autonomous_mode_toggle", "authorization_system", "encryption_layer", "disaster_recovery_manager",
    "redundant_backup_system", "recursive_self_improvement", "printer_3d_control", "robotic_arm_ros2",
    "cnc_machine_control", "workflow_automation", "task_scheduling", "trigger_based_actions",
    "load_testing_engine", "red_team_safety_tester", "automated_testing_sandbox", "version_control_integration",
    "quantized_model_hot_swap", "precision_scalability_switch", "gradual_scaling_controller",
    "human_review_gate", "multi_user_collaboration",
}

# Deterministic features the Hub can re-execute to verify a worker's answer.
SPOT_CHECKABLE: Set[str] = {
    "data_analysis", "feedback_loop_guard", "output_format_enforcer", "input_sanitization_layer",
    "emotional_tone_detection", "virtual_experiment_simulator", "trend_forecasting",
}
_VOLATILE_KEYS = {"input_flags"}
TASK_TTL_S = 3600.0


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def compute_hmac(key: str, payload: Any) -> str:
    return hmac.new(key.encode("utf-8"), _canonical(payload), hashlib.sha256).hexdigest()


def _comparable(result: Any) -> Any:
    if isinstance(result, dict):
        return {k: v for k, v in result.items() if k not in _VOLATILE_KEYS}
    return result


def _spot_checkable(feature: str, payload: dict) -> bool:
    if feature not in SPOT_CHECKABLE:
        return False
    if feature == "trend_forecasting":
        return isinstance(payload.get("series") or payload.get("data"), list)
    if feature == "virtual_experiment_simulator":
        return not payload.get("code")
    return True


@dataclass
class WorkerNodeRecord:
    worker_id: str
    key: str = field(repr=False)
    url: str = "local"
    status: str = "ACTIVE"  # ACTIVE | SLASHED
    credits: int = 100
    burned_credits: int = 0
    tasks_completed: int = 0
    tasks_verified: int = 0
    rejected_packets: int = 0
    registered_at: float = field(default_factory=time.time)
    slashed_reason: str = ""

    def to_dict(self, include_key: bool = False) -> dict:
        d = dataclasses.asdict(self)
        if not include_key:
            d.pop("key")
        return d


class MasterHubCoordinator:
    """Runs only on the owner's Hub: issues signed tasks, verifies proofs, spot-checks, rewards and slashes."""

    def __init__(self, ledger: HashChainLedger, grid: Any = None, state_path: Optional[Path] = None,
                 reward_per_task: int = 25, spot_check_rate: float = 1.0):
        self.ledger = ledger
        self.grid = grid  # used for spot-check re-execution
        self.reward_per_task = reward_per_task
        self.spot_check_rate = spot_check_rate
        self._path = state_path
        self._workers: Dict[str, WorkerNodeRecord] = {}
        self._pending: Dict[str, dict] = {}
        self._lock = threading.RLock()
        self._load()

    # -- persistence
    def _load(self) -> None:
        if self._path and self._path.exists():
            for d in json.loads(self._path.read_text(encoding="utf-8")):
                self._workers[d["worker_id"]] = WorkerNodeRecord(**d)

    def _flush(self) -> None:
        if not self._path:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps([w.to_dict(include_key=True) for w in self._workers.values()]), encoding="utf-8")
        tmp.replace(self._path)
        try:
            os.chmod(self._path, 0o600)
        except OSError:
            pass

    # -- registry
    def register_worker(self, worker_id: str, url: str = "local", initial_credits: int = 100) -> WorkerNodeRecord:
        with self._lock:
            existing = self._workers.get(worker_id)
            if existing and existing.status == "SLASHED":
                raise PermissionError(f"Worker {worker_id!r} is blacklisted (slashed: {existing.slashed_reason})")
            if existing:
                raise ValueError(f"Worker {worker_id!r} already registered")
            rec = WorkerNodeRecord(worker_id=worker_id, key=secrets.token_hex(32), url=url, credits=initial_credits)
            self._workers[worker_id] = rec
            self._flush()
            self.ledger.append("worker_registered", {"worker_id": worker_id, "url": url, "credits": initial_credits})
            return rec

    def get_worker(self, worker_id: str) -> Optional[WorkerNodeRecord]:
        with self._lock:
            return self._workers.get(worker_id)

    def worker_key(self, worker_id: str) -> str:
        rec = self.get_worker(worker_id)
        if not rec:
            raise KeyError(f"Unknown worker {worker_id!r}")
        return rec.key

    def list_workers(self) -> List[dict]:
        with self._lock:
            return [w.to_dict() for w in self._workers.values()]

    # -- tasks
    def create_signed_task(self, worker_id: str, feature_key: str, payload: dict) -> dict:
        with self._lock:
            worker = self._workers.get(worker_id)
            if not worker:
                raise KeyError(f"Unknown worker node {worker_id!r}")
            if worker.status == "SLASHED":
                raise PermissionError(f"Worker {worker_id!r} is SLASHED and blocked")
            if feature_key in HUB_ONLY_FEATURES:
                raise PermissionError(f"Feature {feature_key!r} is a Hub-only power and cannot be delegated")
            envelope = {"task_id": secrets.token_hex(8), "worker_id": worker_id, "feature": feature_key,
                        "payload": payload, "issued_at": time.time(), "nonce": secrets.token_hex(8)}
            packet = {**envelope, "hub_signature": compute_hmac(worker.key, envelope)}
            self._pending[envelope["task_id"]] = packet
            return packet

    def _reject(self, worker: Optional[WorkerNodeRecord], reason: str) -> dict:
        if worker:
            worker.rejected_packets += 1
            self._flush()
        return {"status": "REJECTED", "reason": reason,
                "note": "Unattributable failures are rejected, never slashed."}

    def verify_and_settle(self, response: dict) -> dict:
        task_id = str(response.get("task_id", ""))
        worker_id = str(response.get("worker_id", ""))
        result = response.get("result")
        with self._lock:
            worker = self._workers.get(worker_id)
            if not worker:
                return self._reject(None, "unknown_worker")
            if worker.status == "SLASHED":
                return {"status": "BLOCKED", "reason": "worker_already_slashed"}
            task = self._pending.get(task_id)
            if not task or task["worker_id"] != worker_id:
                return self._reject(worker, "unknown_replayed_or_mismatched_task")
            if time.time() - task["issued_at"] > TASK_TTL_S:
                self._pending.pop(task_id, None)
                return self._reject(worker, "task_expired")
            proof_body = {"task_id": task_id, "worker_id": worker_id, "feature": task["feature"],
                          "nonce": task["nonce"], "result": result}
            if not hmac.compare_digest(str(response.get("worker_proof", "")), compute_hmac(worker.key, proof_body)):
                return self._reject(worker, "invalid_proof_signature")
            self._pending.pop(task_id, None)  # proof is authentic -> task consumed (replay-safe)

        verified = False
        if self.grid is not None and _spot_checkable(task["feature"], task["payload"]) \
                and secrets.randbelow(10_000) < int(self.spot_check_rate * 10_000):
            expected = self.grid.registry.get(task["feature"]).handler(self.grid, sanitize_payload(task["payload"])[0])
            if _canonical(_comparable(expected)) != _canonical(_comparable(result)):
                with self._lock:
                    return self._slash(worker, f"spot_check_mismatch on {task['feature']} (task {task_id})")
            verified = True

        with self._lock:
            worker.credits += self.reward_per_task
            worker.tasks_completed += 1
            worker.tasks_verified += int(verified)
            self._flush()
            block = self.ledger.append("worker_task_settled", {
                "task_id": task_id, "worker_id": worker_id, "feature": task["feature"], "verified": verified,
                "reward": self.reward_per_task, "balance": worker.credits})
            return {"status": "SETTLED", "verified": verified, "worker_id": worker_id, "task_id": task_id,
                    "reward_credits": self.reward_per_task, "total_credits": worker.credits,
                    "ledger_block": block["hash"][:16], "result": result}

    def _slash(self, worker: WorkerNodeRecord, reason: str) -> dict:
        burned, worker.credits = worker.credits, 0
        worker.burned_credits += burned
        worker.status = "SLASHED"
        worker.slashed_reason = reason
        self._flush()
        block = self.ledger.append("worker_slashed", {"worker_id": worker.worker_id, "reason": reason,
                                                      "burned_credits": burned})
        return {"status": "SLASHED", "worker_id": worker.worker_id, "reason": reason, "burned_credits": burned,
                "remaining_credits": 0, "ledger_block": block["hash"][:16]}

    def dispatch_remote(self, worker_id: str, feature_key: str, payload: dict, timeout: float = 120.0) -> dict:
        worker = self.get_worker(worker_id)
        if not worker or worker.url == "local":
            raise ValueError("worker has no remote URL")
        packet = self.create_signed_task(worker_id, feature_key, payload)
        req = urllib.request.Request(worker.url.rstrip("/") + "/worker/execute", data=_canonical(packet),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                response = json.loads(resp.read())
        except (urllib.error.URLError, OSError, ValueError) as exc:
            with self._lock:
                self._pending.pop(packet["task_id"], None)
            return {"status": "UNREACHABLE", "error": str(exc)[:200]}
        return self.verify_and_settle(response)


class LightweightWorkerNode:
    """Edge worker. Holds only its own key; refuses unsigned tasks and Hub-only features; executes through the
    local safety pipeline (sanitization + constitutional rules) and signs the result."""

    def __init__(self, worker_id: str, worker_key: str, executor: Any):
        if not worker_key or len(worker_key) < 32:
            raise ValueError("worker_key must be the key issued by the Hub at registration")
        self.worker_id = worker_id
        self._key = worker_key
        self._executor = executor
        self.registry: FeatureRegistry = build_registry()

    def allowed_features(self) -> List[str]:
        return [f.key for f in self.registry.all() if f.key not in HUB_ONLY_FEATURES]

    def _reply(self, packet: dict, result: dict, sign: bool) -> dict:
        out = {"task_id": packet.get("task_id"), "worker_id": self.worker_id,
               "feature": packet.get("feature"), "result": result, "worker_proof": ""}
        if sign:
            out["worker_proof"] = compute_hmac(self._key, {
                "task_id": packet.get("task_id"), "worker_id": self.worker_id, "feature": packet.get("feature"),
                "nonce": packet.get("nonce"), "result": result})
        return out

    def execute_signed_task(self, packet: dict) -> dict:
        envelope = {k: packet.get(k) for k in ("task_id", "worker_id", "feature", "payload", "issued_at", "nonce")}
        if not hmac.compare_digest(str(packet.get("hub_signature", "")), compute_hmac(self._key, envelope)):
            return self._reply(packet, {"status": "UNAUTHORIZED_HUB", "error": "invalid Hub signature"}, sign=False)
        if envelope["worker_id"] != self.worker_id:
            return self._reply(packet, {"status": "ERROR", "error": "worker_id mismatch"}, sign=False)
        feature_key = str(envelope["feature"])
        if feature_key in HUB_ONLY_FEATURES:
            return self._reply(packet, {"status": "DENIED", "error": "Hub-only feature"}, sign=True)
        payload = envelope["payload"] if isinstance(envelope["payload"], dict) else {}
        if hasattr(self._executor, "run_feature"):
            result = self._executor.run_feature(self._executor.owner_tg_id, feature_key, payload,
                                                via="hub_task", log=False)
        else:
            result = self.registry.get(feature_key).handler(self._executor, sanitize_payload(payload)[0])
        return self._reply(packet, result if isinstance(result, dict) else {"status": "OK", "output": result},
                           sign=True)
