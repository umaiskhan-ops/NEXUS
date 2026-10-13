"""Hybrid Hub-and-Spoke Architecture: Master Hub Coordinator, Lightweight Worker Node,
Cryptographic Task Signing, and Automated Slashing Logic."""
from __future__ import annotations

import dataclasses
import hashlib
import hmac
import json
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .features import FeatureRegistry, Kind, build_registry
from .ledger import HashChainLedger
from .security import Role, sanitize_payload

# Features strictly reserved for the Master Hub (Federal Powers, Governance, Security & Budget Control).
# Worker nodes are physically barred from executing these features.
HUB_ONLY_FEATURES: Set[str] = {
    "mission_control",
    "veto_power",
    "approval_gates",
    "full_transparency_ledger",
    "emergency_override",
    "shutdown_authority",
    "access_control",
    "mission_change_rollbacks",
    "simulation_rollback",
    "grid_state_rollback",
    "final_say_protocol",
    "kill_switch_protocol",
    "token_budget_controller",
    "autonomous_mode_toggle",
    "authorization_system",
    "encryption_layer",
    "disaster_recovery_manager",
    "redundant_backup_system",
    "recursive_self_improvement",
    "printer_3d_control",
    "robotic_arm_ros2",
    "cnc_machine_control",
}


def _canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def compute_hmac(secret: str, payload: Any) -> str:
    return hmac.new(secret.encode("utf-8"), _canonical_bytes(payload), hashlib.sha256).hexdigest()


@dataclass
class WorkerNodeRecord:
    worker_id: str
    url: str = "local"
    status: str = "ACTIVE"  # ACTIVE | SLASHED | OFFLINE
    credits: int = 100      # Initial stake / starting compute credits
    burned_credits: int = 0
    tasks_completed: int = 0
    registered_at: float = field(default_factory=time.time)
    slashed_reason: str = ""

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


class MasterHubCoordinator:
    """Runs exclusively on the Owner's Master Hub.
    Signs outbound tasks, verifies inbound Worker proofs, rewards valid work, and slashes tampered nodes."""

    def __init__(self, ledger: HashChainLedger, shared_secret: str, reward_per_task: int = 25):
        self.ledger = ledger
        self._secret = shared_secret or "sovereign-hub-default-secret"
        self.reward_per_task = reward_per_task
        self._workers: Dict[str, WorkerNodeRecord] = {}
        self._blacklist: Set[str] = set()
        self._pending_tasks: Dict[str, dict] = {}
        self._lock = threading.RLock()

    def register_worker(self, worker_id: str, url: str = "local", initial_credits: int = 100) -> WorkerNodeRecord:
        with self._lock:
            if worker_id in self._blacklist:
                raise PermissionError(f"Worker {worker_id!r} is blacklisted due to prior slashing")
            rec = WorkerNodeRecord(worker_id=worker_id, url=url, credits=initial_credits)
            self._workers[worker_id] = rec
            self.ledger.append("worker_registered", {"worker_id": worker_id, "url": url, "credits": initial_credits})
            return rec

    def get_worker(self, worker_id: str) -> Optional[WorkerNodeRecord]:
        with self._lock:
            return self._workers.get(worker_id)

    def list_workers(self) -> List[dict]:
        with self._lock:
            return [w.to_dict() for w in self._workers.values()]

    def create_signed_task(self, worker_id: str, feature_key: str, payload: dict) -> dict:
        """Creates a cryptographically signed task envelope to send to a Worker Node."""
        with self._lock:
            worker = self._workers.get(worker_id)
            if not worker:
                raise KeyError(f"Unknown worker node {worker_id!r}")
            if worker_id in self._blacklist or worker.status == "SLASHED":
                raise PermissionError(f"Worker {worker_id!r} is SLASHED and blocked from network communications")
            if feature_key in HUB_ONLY_FEATURES:
                raise PermissionError(f"Feature {feature_key!r} is a Master Hub Federal Power and cannot be delegated")

            task_id = secrets.token_hex(6)
            envelope = {
                "task_id": task_id,
                "worker_id": worker_id,
                "feature": feature_key,
                "payload": payload,
                "issued_at": time.time(),
            }
            signature = compute_hmac(self._secret, envelope)
            signed_packet = {**envelope, "hub_signature": signature}
            self._pending_tasks[task_id] = signed_packet
            return signed_packet

    def verify_and_settle(self, response_packet: dict) -> dict:
        """Verifies the state proof returned by a Worker Node.
        If valid -> rewards credits.
        If invalid/corrupted -> SLASHES the worker (burns credits, invalidates ID, blocks communications)."""
        task_id = response_packet.get("task_id", "")
        worker_id = response_packet.get("worker_id", "")
        result = response_packet.get("result")
        worker_proof = response_packet.get("worker_proof", "")

        with self._lock:
            worker = self._workers.get(worker_id)
            if not worker:
                return {"status": "REJECTED", "reason": "unknown_worker"}
            if worker_id in self._blacklist or worker.status == "SLASHED":
                return {"status": "BLOCKED", "reason": "worker_already_slashed"}

            expected_task = self._pending_tasks.get(task_id)
            if not expected_task or expected_task["worker_id"] != worker_id:
                return self._slash_worker(worker, f"unrecognized or mismatched task_id {task_id!r}")

            # Recompute expected cryptographic proof over (task_id, worker_id, feature, result)
            proof_body = {
                "task_id": task_id,
                "worker_id": worker_id,
                "feature": expected_task["feature"],
                "result": result,
            }
            expected_proof = compute_hmac(self._secret, proof_body)

            if not hmac.compare_digest( str(worker_proof), expected_proof):
                return self._slash_worker(worker, "corrupted_or_tampered_state_proof")

            if not isinstance(result, dict) or result.get("status") in {"TAMPERED", "UNAUTHORIZED_HUB"}:
                return self._slash_worker(worker, "invalid_execution_state")

            # Valid proof: settle task and reward compute credits
            self._pending_tasks.pop(task_id, None)
            worker.credits += self.reward_per_task
            worker.tasks_completed += 1
            block = self.ledger.append("worker_task_settled", {
                "task_id": task_id,
                "worker_id": worker_id,
                "feature": expected_task["feature"],
                "reward": self.reward_per_task,
                "new_balance": worker.credits,
            })
            return {
                "status": "SETTLED",
                "worker_id": worker_id,
                "task_id": task_id,
                "reward_credits": self.reward_per_task,
                "total_credits": worker.credits,
                "ledger_block": block["hash"][:16],
                "result": result,
            }

    def _slash_worker(self, worker: WorkerNodeRecord, reason: str) -> dict:
        """Executes immediate slashing penalty: burns all credits, invalidates ID, and blacklists node."""
        burned = worker.credits
        worker.credits = 0
        worker.burned_credits += burned
        worker.status = "SLASHED"
        worker.slashed_reason = reason
        self._blacklist.add(worker.worker_id)

        block = self.ledger.append("worker_slashed", {
            "worker_id": worker.worker_id,
            "reason": reason,
            "burned_credits": burned,
            "timestamp": time.time(),
        })
        return {
            "status": "SLASHED",
            "worker_id": worker.worker_id,
            "reason": reason,
            "burned_credits": burned,
            "remaining_credits": 0,
            "ledger_block": block["hash"][:16],
        }


class LightweightWorkerNode:
    """Stateless edge Worker Node (Spoke) for external servers.
    Contains NO Federal Powers or governance keys. Only executes Hub-signed tasks and returns proofs."""

    def __init__(self, worker_id: str, shared_secret: str, grid_executor: Any):
        self.worker_id = worker_id
        self._secret = shared_secret or "sovereign-hub-default-secret"
        self._executor = grid_executor
        self.registry: FeatureRegistry = build_registry()

    def allowed_features(self) -> List[str]:
        return [f.key for f in self.registry.all() if f.key not in HUB_ONLY_FEATURES]

    def execute_signed_task(self, signed_packet: dict) -> dict:
        """Verifies the Master Hub's signature, runs the allowed worker task, and signs the output proof."""
        hub_sig = signed_packet.get("hub_signature", "")
        envelope = {
            "task_id": signed_packet.get("task_id"),
            "worker_id": signed_packet.get("worker_id"),
            "feature": signed_packet.get("feature"),
            "payload": signed_packet.get("payload"),
            "issued_at": signed_packet.get("issued_at"),
        }
        expected_sig = compute_hmac(self._secret, envelope)
        if not hmac.compare_digest(str(hub_sig), expected_sig):
            return {
                "task_id": envelope["task_id"],
                "worker_id": self.worker_id,
                "result": {"status": "UNAUTHORIZED_HUB", "error": "invalid Master Hub signature"},
                "worker_proof": "",
            }

        if envelope["worker_id"] != self.worker_id:
            return {
                "task_id": envelope["task_id"],
                "worker_id": self.worker_id,
                "result": {"status": "ERROR", "error": "worker_id mismatch"},
                "worker_proof": "",
            }

        feature_key = envelope["feature"]
        if feature_key in HUB_ONLY_FEATURES:
            return {
                "task_id": envelope["task_id"],
                "worker_id": self.worker_id,
                "result": {"status": "DENIED", "error": "Federal Power features are restricted to the Master Hub"},
                "worker_proof": "",
            }

        clean_payload, _ = sanitize_payload(envelope["payload"] or {})
        feature = self.registry.get(feature_key)
        try:
            result = feature.handler(self._executor, clean_payload)
            if not isinstance(result, dict):
                result = {"status": "OK", "output": result}
            result.setdefault("status", "OK")
        except Exception as exc:  # noqa: BLE001
            result = {"status": "ERROR", "error": str(exc)[:300]}

        proof_body = {
            "task_id": envelope["task_id"],
            "worker_id": self.worker_id,
            "feature": feature_key,
            "result": result,
        }
        proof = compute_hmac(self._secret, proof_body)
        return {
            "task_id": envelope["task_id"],
            "worker_id": self.worker_id,
            "feature": feature_key,
            "result": result,
            "worker_proof": proof,
        }
