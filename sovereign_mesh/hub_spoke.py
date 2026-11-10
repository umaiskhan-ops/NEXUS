"""Hybrid Hub-and-Spoke: the Master Hub keeps all governance; edge Workers only execute signed tasks.

Security model (read this before relying on slashing):
  * Every worker gets its OWN random key at registration (no shared secret). A valid proof is therefore
    attributable: only the Hub and that one worker know the key.
  * An INVALID proof is rejected but never slashed, because it cannot be attributed (anyone can send garbage
    in someone else's name; slashing on that would let attackers burn honest workers' credits).
  * Slashing happens only on PROVABLE misbehaviour: a correctly-signed result that disagrees with the Hub's own
    re-execution (spot-check) of a deterministic feature.
  * Non-deterministic (LLM) results are validated via schema, non-empty output commitment, and constitutional
    sanitization; any unverified or invalid result (`verified: false`) is rejected and never rewarded.
  * Credits are an internal accounting number, not money or a token.
"""
from __future__ import annotations

import dataclasses
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .features import FeatureRegistry, build_registry
from .ledger import HashChainLedger, interprocess_file_lock
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


def compute_cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Computes exact mathematical Cosine Similarity between two float32 vectors: (u · v) / (||u|| ||v||)."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = 0.0
    norm_a_sq = 0.0
    norm_b_sq = 0.0
    for a, b in zip(vec_a, vec_b):
        if math.isnan(a) or math.isnan(b) or math.isinf(a) or math.isinf(b):
            return 0.0
        dot += a * b
        norm_a_sq += a * a
        norm_b_sq += b * b
    if norm_a_sq <= 1e-12 or norm_b_sq <= 1e-12:
        return 0.0
    return max(-1.0, min(1.0, dot / (math.sqrt(norm_a_sq) * math.sqrt(norm_b_sq))))


_STOPWORDS: Set[str] = {
    # English common grammatical / function words
    "the", "a", "an", "is", "are", "was", "were", "and", "or", "but", "in", "on", "at",
    "to", "for", "of", "with", "by", "as", "from", "that", "this", "it", "its", "be",
    "have", "has", "had", "do", "does", "did", "can", "could", "will", "would", "shall",
    "should", "may", "might", "must", "they", "them", "their", "we", "us", "our", "you",
    "your", "he", "him", "his", "she", "her", "i", "me", "my", "so", "than", "then",
    "there", "here", "when", "where", "why", "how", "all", "any", "both", "each", "few",
    "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same",
    "too", "very", "about", "above", "after", "again", "against", "between", "into",
    "through", "during", "before", "under", "below", "up", "down", "over", "just",
    "what", "which", "who", "whom", "these", "those", "am", "been", "being",
    # Roman Urdu common function words
    "hai", "hain", "ke", "ki", "ko", "se", "par", "ka", "kya", "ye", "woh", "aur",
    "bhi", "tha", "thi", "the", "kar", "karna", "hoti", "hota", "hote", "mein", "main",
    "ab", "jab", "tab", "kuch", "apne", "apna", "apni", "humein", "unhein", "unka",
}
CONSENSUS_BUFFER_TTL = 300.0  # Seconds before unverified freeform candidate entries expire


def extract_content_tokens(text: str) -> List[str]:
    """Extracts meaningful, non-stopword content tokens from response text."""
    raw = re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", (text or "").lower())
    return [t for t in raw if t not in _STOPWORDS and not t.isdigit()]


def compute_content_cosine_similarity(text1: str, text2: str) -> float:
    """Computes exact cosine similarity over substantive content word vectors."""
    t1 = extract_content_tokens(text1)
    t2 = extract_content_tokens(text2)
    if len(t1) < 4 or len(t2) < 4:
        return 0.0

    from collections import Counter
    vec1 = Counter(t1)
    vec2 = Counter(t2)
    all_keys = set(vec1.keys()) | set(vec2.keys())

    dot = sum(vec1.get(k, 0) * vec2.get(k, 0) for k in all_keys)
    norm1_sq = sum(v * v for v in vec1.values())
    norm2_sq = sum(v * v for v in vec2.values())
    if norm1_sq <= 1e-12 or norm2_sq <= 1e-12:
        return 0.0
    return dot / (math.sqrt(norm1_sq) * math.sqrt(norm2_sq))


def _is_independent_peer(w1: WorkerNodeRecord, w2: WorkerNodeRecord) -> bool:
    """Verifies that two workers are genuinely independent nodes (Anti-Sybil Separation)."""
    if not w1 or not w2:
        return False
    if w1.worker_id == w2.worker_id:
        return False
    if w1.hardware_uuid and w2.hardware_uuid and w1.hardware_uuid == w2.hardware_uuid:
        return False
    ip1 = (getattr(w1, "public_ip", "") or "").strip()
    ip2 = (getattr(w2, "public_ip", "") or "").strip()
    local_hosts = {"", "local", "127.0.0.1", "localhost", "::1"}
    if ip1 not in local_hosts and ip2 not in local_hosts:
        if ip1 == ip2:
            return False
        # Check /24 IPv4 subnet
        sub1 = ".".join(ip1.split(".")[:3]) if "." in ip1 else ip1
        sub2 = ".".join(ip2.split(".")[:3]) if "." in ip2 else ip2
        if sub1 == sub2:
            return False
    # Check referral collusion
    if getattr(w1, "referred_by", "") and w1.referred_by == w2.worker_id:
        return False
    if getattr(w2, "referred_by", "") and w2.referred_by == w1.worker_id:
        return False
    return True


def _comparable(result: Any) -> Any:
    if isinstance(result, dict):
        return {k: v for k, v in result.items() if k not in _VOLATILE_KEYS}
    return result


def _spot_checkable(feature: str, payload: dict) -> bool:
    if feature not in SPOT_CHECKABLE:
        return False
    if not isinstance(payload, dict):
        return False
    if feature == "trend_forecasting":
        return isinstance(payload.get("series") or payload.get("data"), list)
    if feature == "data_analysis":
        return bool(payload.get("series") or payload.get("data") or payload.get("numbers"))
    if feature == "virtual_experiment_simulator":
        return not payload.get("code")
    return True


WELCOME_CREDITS = 20
REFERRAL_BONUS_RATE = 0.05  # +5% extra bonus credits minted to referrer when referred worker mines/completes tasks
POW_DIFFICULTY = int(os.environ.get("NEXUS_POW_DIFFICULTY", "4"))  # SHA-256 hex prefix difficulty (~65,536 hashes default, scales up to 6)


def dynamic_pow_difficulty(active_workers: int = 1) -> int:
    """Dynamically scales Micro-PoW difficulty based on network size (N4 Anti-Sybil Fix)."""
    if active_workers > 500:
        return max(POW_DIFFICULTY, 6)
    if active_workers > 50:
        return max(POW_DIFFICULTY, 5)
    return POW_DIFFICULTY


def solve_pow_challenge(worker_id: str, challenge: str, difficulty: int = POW_DIFFICULTY) -> str:
    """Solves the Hub's Micro-PoW challenge by burning real CPU SHA-256 cycles."""
    prefix = "0" * max(1, int(difficulty))
    nonce = 0
    base = f"{worker_id}:{challenge}:"
    while True:
        candidate = f"{base}{nonce}".encode("utf-8")
        if hashlib.sha256(candidate).hexdigest().startswith(prefix):
            return str(nonce)
        nonce += 1


def verify_pow_solution(worker_id: str, challenge: str, nonce: str, difficulty: int = POW_DIFFICULTY) -> bool:
    """Verifies a worker's Micro-PoW solution for a heartbeat ping (N4 Fix: strict difficulty check, no '00' fallback)."""
    if not challenge or nonce is None or str(nonce).strip() == "":
        return False
    prefix = "0" * max(1, int(difficulty))
    digest = hashlib.sha256(f"{worker_id}:{challenge}:{str(nonce).strip()}".encode("utf-8")).hexdigest()
    return digest.startswith(prefix)


def _ip_subnet_prefix(ip_str: str) -> str:
    """Extracts /24 IPv4 or /48 IPv6 subnet prefix to mitigate proxy/VPN rotation within the same ASN block (N4 Fix)."""
    clean = (ip_str or "").strip()
    if not clean or clean in {"127.0.0.1", "localhost", "::1", "local"}:
        return ""
    if "." in clean:
        parts = clean.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
    if ":" in clean:
        hextets = clean.split(":")
        return ":".join(hextets[:3]) + "::/48"
    return clean


@dataclass
class WorkerNodeRecord:
    worker_id: str
    key: str = field(repr=False)
    url: str = "local"
    status: str = "ACTIVE"  # ACTIVE | SLASHED
    credits: int = WELCOME_CREDITS
    welcome_credits_locked: int = 0
    burned_credits: int = 0
    tasks_completed: int = 0
    tasks_verified: int = 0
    rejected_packets: int = 0
    registered_at: float = field(default_factory=time.time)
    slashed_reason: str = ""
    payout_address: str = ""
    total_payout_earned: float = 0.0
    pending_payout: float = 0.0
    epoch_tasks_verified: int = 0
    uptime_minutes_verified: int = 0
    last_heartbeat_reward_at: float = field(default_factory=time.time)
    # Anti-Sybil & Hardware Rig Specs
    hardware_uuid: str = ""
    public_ip: str = ""
    hardware_spec: str = "Standard Multi-Core Rig"
    # Anti-Fake-Uptime Micro-PoW
    pow_challenge: str = field(default_factory=lambda: secrets.token_hex(8))
    pow_verified_count: int = 0
    # P2P Dispute Freeze (H6: order-scoped freeze by default; account lock only for accused scammer)
    dispute_frozen: bool = False
    dispute_account_locked: bool = False
    dispute_escrow_locked_credits: int = 0
    dispute_reason: str = ""
    # Viral Referral Multiplier (+5% Network Effect)
    referral_code: str = ""
    referred_by: str = ""
    referrals_count: int = 0
    referral_bonus_credits: int = 0
    referral_bonus_accumulator: float = 0.0
    # Decentralized Brain Matrix Sharding & P2P Delta Sync
    brain_shard: str = "DATA_MEMORY_SYNTHESIS"
    replica_shards: List[str] = field(default_factory=lambda: ["CODE_DEBUG_EXEC", "MATH_PROOF_LOGIC"])
    synced_deltas_count: int = 0
    protocol_version: str = "2026.5.0"
    # Multi-Chamber 4096-Bit Hybrid Cryptographic Identity (HSQK-4096)
    quantum_address: str = ""
    crypto_security_level: str = "4096-Bit Hybrid Lattice + Ed448 + SHA3-512 Key Vault"
    puf_seal: str = ""
    quantum_vault_pub: Dict[str, Any] = field(default_factory=dict)
    ratchet_step: int = 0
    daily_task_credits_earned: int = 0
    daily_task_window_start: float = 0.0

    def __post_init__(self) -> None:
        if not self.referral_code:
            self.referral_code = f"REF-{self.worker_id.upper()}"
        if not self.pow_challenge:
            self.pow_challenge = secrets.token_hex(8)
        if not self.brain_shard:
            from .brain_matrix import assign_worker_brain_shard
            sh = assign_worker_brain_shard(4, self.hardware_spec, self.worker_id)
            self.brain_shard = sh["primary_shard"]
            self.replica_shards = sh["replica_shards"]
        if not self.quantum_address:
            try:
                from .quantum_crypto import encode_quantum_address, ADDRESS_HRP
                seed = hashlib.blake2b(f"{self.worker_id}:{self.key}".encode("utf-8"), digest_size=32).digest()
                self.quantum_address = encode_quantum_address(ADDRESS_HRP, seed)
            except Exception:
                self.quantum_address = f"nxq1{self.worker_id.replace('-', '')[:16]}q000"

    def to_dict(self, include_key: bool = False) -> dict:
        d = dataclasses.asdict(self)
        if not include_key:
            d.pop("key")
        return d


class MasterHubCoordinator:
    """Runs only on the owner's Hub: issues signed tasks, verifies proofs, spot-checks, rewards and slashes."""

    def __init__(self, ledger: HashChainLedger, grid: Any = None, state_path: Optional[Path] = None,
                 reward_per_task: int = 25, spot_check_rate: float = 1.0, gradient_spot_check_rate: float = 1.0):
        self.ledger = ledger
        self.grid = grid  # used for spot-check re-execution
        self.reward_per_task = reward_per_task
        self.spot_check_rate = spot_check_rate
        self.gradient_spot_check_rate = gradient_spot_check_rate
        self.force_gradient_spot_check = True
        self.max_referral_cap = 500
        self.max_workers_per_ip = 3
        self.max_daily_task_credits = 250
        self._path = state_path
        self._workers: Dict[str, WorkerNodeRecord] = {}
        self._pending: Dict[str, dict] = {}
        self._nat_outbound_queue: Dict[str, List[dict]] = {}
        self._nat_in_flight: Dict[str, dict] = {}
        self._nat_task_events: Dict[str, threading.Event] = {}
        self._nat_settled_results: Dict[str, dict] = {}
        self._freeform_consensus: Dict[str, dict] = {}
        self.commercial_revenue_pool: float = 0.0
        self.treasury_balance: float = 0.0
        self.current_epoch: int = 1
        self._lock = threading.RLock()
        self._load()

    # -- persistence & WAL crash-recovery (H4 / M7 Fix)
    def _load(self) -> None:
        last_settled_hash = ""
        if self._path and self._path.exists():
            try:
                with interprocess_file_lock(self._path):
                    data = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.commercial_revenue_pool = float(data.get("commercial_revenue_pool", 0.0))
                    self.treasury_balance = float(data.get("treasury_balance", 0.0))
                    self.current_epoch = int(data.get("current_epoch", 1))
                    last_settled_hash = str(data.get("last_settled_ledger_hash", ""))
                    workers_data = data.get("workers", [])
                else:
                    workers_data = data
                valid_fields = {f.name for f in dataclasses.fields(WorkerNodeRecord)}
                for d in workers_data:
                    filtered = {k: v for k, v in d.items() if k in valid_fields}
                    self._workers[d["worker_id"]] = WorkerNodeRecord(**filtered)
            except Exception:
                pass
        self._reconcile_wal_from_ledger(last_settled_hash)

    def _reconcile_wal_from_ledger(self, last_settled_hash: str) -> None:
        """Replays any uncommitted WAL credit transitions from HashChainLedger after a process crash (H4 Fix)."""
        if not self.ledger or not self._workers:
            return
        try:
            blocks = self.ledger.range(0, len(self.ledger))
            if not blocks:
                return
            start_idx = 0
            if last_settled_hash:
                found = False
                for idx, b in enumerate(blocks):
                    if b.get("hash") == last_settled_hash:
                        start_idx = idx + 1
                        found = True
                        break
                if not found:
                    return
            else:
                return
            reconciled = False
            for b in blocks[start_idx:]:
                task = b.get("data", {}).get("task", "")
                p = b.get("data", {}).get("payload", {})
                if task == "credits_spent":
                    w = self._workers.get(p.get("worker_id", ""))
                    if w and "remaining" in p and w.credits != int(p["remaining"]):
                        w.credits = int(p["remaining"])
                        reconciled = True
                elif task == "owner_credits_granted":
                    w = self._workers.get(p.get("worker_id", ""))
                    if w and "new_balance" in p and w.credits != int(p["new_balance"]):
                        w.credits = int(p["new_balance"])
                        reconciled = True
                elif task == "credits_transferred":
                    wf = self._workers.get(p.get("from_worker", ""))
                    wt = self._workers.get(p.get("to_worker", ""))
                    if wf and "from_balance" in p:
                        wf.credits = int(p["from_balance"])
                        reconciled = True
                    if wt and "to_balance" in p:
                        wt.credits = int(p["to_balance"])
                        reconciled = True
            if reconciled:
                self._flush()
        except Exception:
            pass

    def _flush(self) -> None:
        if not self._path:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with interprocess_file_lock(self._path):
            tmp = self._path.with_suffix(".tmp")
            payload = {
                "commercial_revenue_pool": self.commercial_revenue_pool,
                "treasury_balance": self.treasury_balance,
                "current_epoch": self.current_epoch,
                "last_settled_ledger_hash": getattr(self.ledger, "head_hash", "") if self.ledger else "",
                "workers": [w.to_dict(include_key=True) for w in self._workers.values()],
            }
            with tmp.open("w", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, indent=1))
                fh.flush()
                try:
                    os.fsync(fh.fileno())
                except OSError:
                    pass
            tmp.replace(self._path)
            try:
                os.chmod(self._path, 0o600)
            except OSError:
                pass

    def _resolve_referrer(self, ref_code_or_id: str) -> Optional[WorkerNodeRecord]:
        if not ref_code_or_id:
            return None
        cand = str(ref_code_or_id).strip()
        with self._lock:
            if cand in self._workers:
                return self._workers[cand]
            upper = cand.upper()
            for w in self._workers.values():
                if w.referral_code.upper() == upper or w.worker_id.upper() == upper:
                    return w
            return None

    def _award_referral_bonus(self, earner: WorkerNodeRecord, earned_credits: int, source: str) -> int:
        """Awards +5% extra bonus credits to earner's referrer without deducting from earner (capped per N4 Fix)."""
        if not earner.referred_by or earned_credits <= 0:
            return 0
        max_referral_cap = int(getattr(self, "max_referral_cap", 500))
        with self._lock:
            referrer = self._workers.get(earner.referred_by)
            if not referrer or referrer.status != "ACTIVE" or referrer.worker_id == earner.worker_id:
                return 0
            if referrer.referral_bonus_credits >= max_referral_cap:
                return 0
            exact_bonus = float(earned_credits) * REFERRAL_BONUS_RATE
            referrer.referral_bonus_accumulator = round(referrer.referral_bonus_accumulator + exact_bonus, 4)
            if source == "task_settlement":
                # Guarantee at least +1 bonus credit on active task completion (e.g. 5% of 25 = 1.25 -> +1 cr immediately)
                minted = max(1, int(referrer.referral_bonus_accumulator))
                referrer.referral_bonus_accumulator = max(0.0, round(referrer.referral_bonus_accumulator - minted, 4))
            else:
                minted = int(referrer.referral_bonus_accumulator)
                if minted > 0:
                    referrer.referral_bonus_accumulator = round(referrer.referral_bonus_accumulator - minted, 4)
            minted = min(minted, max(0, max_referral_cap - referrer.referral_bonus_credits))
            if minted > 0:
                referrer.credits += minted
                referrer.referral_bonus_credits += minted
                self.ledger.append("referral_bonus_minted", {
                    "referrer_id": referrer.worker_id,
                    "from_referred_worker": earner.worker_id,
                    "source": source,
                    "worker_earned": earned_credits,
                    "bonus_minted": minted,
                    "referrer_new_balance": referrer.credits,
                })
            return minted

    # -- registry
    def register_worker(self, worker_id: str, url: str = "local", initial_credits: int = WELCOME_CREDITS,
                        hardware_uuid: str = "", public_ip: str = "", hardware_spec: str = "",
                        referred_by: str = "", version: str = "",
                        quantum_address: str = "", quantum_vault_pub: Optional[Dict[str, Any]] = None,
                        puf_seal: str = "") -> WorkerNodeRecord:
        from .brain_matrix import assign_worker_brain_shard

        hardware_uuid = (hardware_uuid or "").strip()
        public_ip = (public_ip or "").strip()
        hardware_spec = (hardware_spec or "").strip()
        referred_by = (referred_by or "").strip()
        version = (version or "").strip()
        quantum_address = (quantum_address or "").strip()
        puf_seal = (puf_seal or "").strip()
        quantum_vault_pub = quantum_vault_pub or {}

        with self._lock:
            existing = self._workers.get(worker_id)
            if existing and existing.status == "SLASHED":
                raise PermissionError(f"Worker {worker_id!r} is blacklisted (slashed: {existing.slashed_reason})")
            if existing:
                if url and url != "local":
                    existing.url = url
                if hardware_spec:
                    existing.hardware_spec = hardware_spec
                    sh = assign_worker_brain_shard(4, hardware_spec, worker_id)
                    existing.brain_shard = sh["primary_shard"]
                    existing.replica_shards = sh["replica_shards"]
                if hardware_uuid and not existing.hardware_uuid:
                    existing.hardware_uuid = hardware_uuid
                if version:
                    existing.protocol_version = version
                if quantum_address:
                    existing.quantum_address = quantum_address
                if quantum_vault_pub:
                    existing.quantum_vault_pub = quantum_vault_pub
                if puf_seal:
                    existing.puf_seal = puf_seal
                if referred_by and not existing.referred_by:
                    referrer = self._resolve_referrer(referred_by)
                    if referrer and referrer.worker_id != existing.worker_id:
                        existing.referred_by = referrer.worker_id
                        referrer.referrals_count += 1
                self._flush()
                return existing

            # Anti-Sybil VM & Sandbox Spoofing Guard: block multiple workers with the same hardware_uuid
            if hardware_uuid and worker_id != "owner-master":
                for other in self._workers.values():
                    if other.worker_id != worker_id and other.hardware_uuid and other.hardware_uuid == hardware_uuid:
                        self.ledger.append("sybil_attempt_blocked", {
                            "attempted_worker_id": worker_id,
                            "existing_worker_id": other.worker_id,
                            "hardware_uuid": hardware_uuid,
                            "public_ip": public_ip,
                        })
                        raise PermissionError(
                            f"Anti-Sybil Hardware Guard: Hardware fingerprint {hardware_uuid!r} is already registered to "
                            f"active worker {other.worker_id!r}. Spinning up multiple VMs/clones on 1 PC to farm welcome "
                            f"credits or uptime is strictly blocked."
                        )

            # Anti-Sybil Per-IP Limit (N4 Fix): block mass registration from the same public IP
            if public_ip and public_ip not in {"127.0.0.1", "localhost", "::1", "local"} and worker_id != "owner-master":
                same_ip_count = sum(
                    1 for other in self._workers.values()
                    if other.worker_id != worker_id and other.public_ip == public_ip and other.status == "ACTIVE"
                )
                if same_ip_count >= int(getattr(self, "max_workers_per_ip", 3)):
                    self.ledger.append("sybil_ip_limit_blocked", {
                        "attempted_worker_id": worker_id,
                        "public_ip": public_ip,
                        "existing_count": same_ip_count,
                    })
                    raise PermissionError(
                        f"Anti-Sybil IP Guard (N4): Maximum workers ({self.max_workers_per_ip}) per public IP ({public_ip}) exceeded."
                    )
                subnet = _ip_subnet_prefix(public_ip)
                if subnet:
                    same_subnet_count = sum(
                        1 for other in self._workers.values()
                        if other.worker_id != worker_id and other.status == "ACTIVE" and _ip_subnet_prefix(other.public_ip) == subnet
                    )
                    max_subnet = int(getattr(self, "max_workers_per_subnet", 5))
                    if same_subnet_count >= max_subnet:
                        self.ledger.append("sybil_subnet_limit_blocked", {
                            "attempted_worker_id": worker_id,
                            "public_ip": public_ip,
                            "subnet": subnet,
                            "existing_count": same_subnet_count,
                        })
                        raise PermissionError(
                            f"Anti-Sybil Subnet Guard (N4): Maximum workers ({max_subnet}) per subnet ({subnet}) exceeded."
                        )

            referrer = self._resolve_referrer(referred_by) if referred_by else None
            ref_wid = referrer.worker_id if (referrer and referrer.worker_id != worker_id) else ""
            eff_spec = hardware_spec or "Standard Multi-Core Rig"
            shard_info = assign_worker_brain_shard(4, eff_spec, worker_id)

            rec = WorkerNodeRecord(
                worker_id=worker_id,
                key=secrets.token_hex(32),
                url=url,
                credits=initial_credits,
                hardware_uuid=hardware_uuid,
                public_ip=public_ip,
                hardware_spec=eff_spec,
                referred_by=ref_wid,
                brain_shard=shard_info["primary_shard"],
                replica_shards=shard_info["replica_shards"],
                protocol_version=version or "2026.5.0",
                quantum_address=quantum_address,
                quantum_vault_pub=quantum_vault_pub or {},
                puf_seal=puf_seal,
            )
            self._workers[worker_id] = rec
            if referrer and ref_wid:
                referrer.referrals_count += 1
            self._flush()
            self.ledger.append("worker_registered", {
                "worker_id": worker_id,
                "url": url,
                "credits": initial_credits,
                "hardware_uuid": hardware_uuid,
                "hardware_spec": rec.hardware_spec,
                "brain_shard": rec.brain_shard,
                "referred_by": ref_wid,
                "quantum_address": rec.quantum_address,
                "crypto_security_level": rec.crypto_security_level,
                "puf_seal_active": bool(rec.puf_seal),
            })
            return rec

    def get_worker_by_key(self, secret_key: str) -> Optional[WorkerNodeRecord]:
        if not secret_key:
            return None
        with self._lock:
            for w in self._workers.values():
                if w.key and hmac.compare_digest(w.key, secret_key):
                    return w
            return None

    def is_public_worker_id(self, candidate: str) -> bool:
        with self._lock:
            w = self._workers.get(candidate)
            return bool(w and w.key != candidate)

    def authenticate_worker_key(self, secret_key: str) -> WorkerNodeRecord:
        """Strictly authenticates a worker by private 64-char secret key, rejecting public worker_ids (C3 Fix)."""
        cand = (secret_key or "").strip()
        if not cand:
            raise PermissionError("Authentication Error (C3): Secret Account Key is required")
        with self._lock:
            if self.is_public_worker_id(cand):
                raise PermissionError(
                    f"Security Error (C3): Public Worker ID {cand!r} cannot be used as an authentication key. "
                    "Use your private 64-character Secret Account Key."
                )
            w = self.get_worker_by_key(cand)
            if not w:
                raise PermissionError("Authentication Error (C3/N3): Invalid or unregistered Secret Account Key")
            if w.status == "SLASHED":
                raise PermissionError(f"Worker {w.worker_id!r} is SLASHED and blacklisted")
            return w

    def get_worker(self, worker_id: str) -> Optional[WorkerNodeRecord]:
        """Strictly looks up a worker by public worker_id only (R3 Fix: never conflates worker_id with secret_key)."""
        with self._lock:
            return self._workers.get(worker_id)

    def _resolve_worker_or_key(self, identifier: str) -> Optional[WorkerNodeRecord]:
        with self._lock:
            return self._workers.get(identifier) or self.get_worker_by_key(identifier)

    def worker_key(self, worker_id: str) -> str:
        rec = self.get_worker(worker_id)
        if not rec:
            raise KeyError(f"Unknown worker {worker_id!r}")
        return rec.key

    def list_workers(self) -> List[dict]:
        with self._lock:
            return [w.to_dict() for w in self._workers.values()]

    # -- Rule 5: Dynamic Bitcoin-Style Halving based on Active Network Workers
    def halving_epoch_info(self) -> dict:
        with self._lock:
            active_workers = sum(1 for w in self._workers.values() if w.status == "ACTIVE")
            if active_workers <= 50:
                era = 1
                label = "Era 1: Genesis Growth (1-50 Workers)"
                multiplier = 1.0
                uptime_interval_s = 1800.0  # 30 mins -> 2 cr/hr (4 cr/hr on 16+ cores)
                next_halving_at = 51
            elif active_workers <= 500:
                era = 2
                label = "Era 2: First Halving 50% (51-500 Workers)"
                multiplier = 0.5
                uptime_interval_s = 3600.0  # 60 mins -> 1 cr/hr (2 cr/hr on 16+ cores)
                next_halving_at = 501
            else:
                era = 3
                label = "Era 3: Sovereign Scarcity 75% Halving (500+ Workers)"
                multiplier = 0.25
                uptime_interval_s = 7200.0  # 120 mins -> 0.5 cr/hr (1 cr/hr on 16+ cores)
                next_halving_at = 5000
            effective_task_reward = max(1, int(self.reward_per_task * multiplier))
            idle_rate_standard = round((3600.0 / uptime_interval_s) * 1.0, 2)
            idle_rate_heavy = round((3600.0 / uptime_interval_s) * 2.0, 2)
            return {
                "era": era,
                "label": label,
                "active_workers": active_workers,
                "multiplier": multiplier,
                "uptime_interval_seconds": uptime_interval_s,
                "idle_credits_per_hour_standard": idle_rate_standard,
                "idle_credits_per_hour_heavy_16c": idle_rate_heavy,
                "idle_credits_per_hour_high_core": idle_rate_heavy,
                "active_task_reward_credits": effective_task_reward,
                "next_halving_at_workers": next_halving_at,
            }

    # -- Rule 1 + Anti-Fake-Uptime Micro-PoW: Slow Idle Uptime Mining (2-4 Credits/Hour)
    def record_heartbeat(self, worker_id: str, cores: int = 4, pow_nonce: Optional[str] = None,
                         hardware_spec: str = "", synced_deltas_count: Optional[int] = None) -> Optional[WorkerNodeRecord]:
        """Awards slow idle uptime credits after verifying optional Micro-PoW challenge."""
        from .brain_matrix import assign_worker_brain_shard

        with self._lock:
            rec = self.get_worker(worker_id)
            if not rec or rec.status == "SLASHED":
                return rec
            if hardware_spec and hardware_spec.strip():
                rec.hardware_spec = hardware_spec.strip()
            if synced_deltas_count is not None:
                try:
                    sdc = int(synced_deltas_count)
                    if sdc > rec.synced_deltas_count:
                        rec.synced_deltas_count = sdc
                except (ValueError, TypeError):
                    pass
            sh = assign_worker_brain_shard(int(cores or 4), rec.hardware_spec, rec.worker_id)
            rec.brain_shard = sh["primary_shard"]
            rec.replica_shards = sh["replica_shards"]
            if pow_nonce is not None:
                if not verify_pow_solution(rec.worker_id, rec.pow_challenge, str(pow_nonce)):
                    rec.rejected_packets += 1
                    self._flush()
                    self.ledger.append("heartbeat_pow_rejected", {
                        "worker_id": rec.worker_id,
                        "supplied_nonce": str(pow_nonce)[:32],
                    })
                    raise PermissionError(
                        "Anti-Fake-Uptime PoW Guard: Invalid Micro-PoW solution for heartbeat ping. "
                        "Fake ping scripts without real CPU hash computation are rejected."
                    )
                rec.pow_verified_count += 1
                rec.pow_challenge = secrets.token_hex(8)
            hinfo = self.halving_epoch_info()
            interval_s = hinfo["uptime_interval_seconds"]  # 1800s (30 mins) in Era 1
            now = time.time()
            last_ts = getattr(rec, "last_reward_time", None) or rec.last_heartbeat_reward_at or rec.registered_at or now
            elapsed = now - last_ts
            if elapsed >= interval_s:
                # Cap intervals per single heartbeat ping to prevent offline clock-jump farming (N4 Fix)
                intervals = min(2, max(1, int(elapsed // interval_s)))
                capped_cores = min(64, max(1, int(cores or 4)))
                hw_multiplier = 2 if capped_cores >= 16 else 1
                earned = intervals * hw_multiplier
                rec.credits += earned
                rec.uptime_minutes_verified += int((intervals * interval_s) // 60)
                rec.last_heartbeat_reward_at = now
                if hasattr(rec, "last_reward_time"):
                    rec.last_reward_time = now
                self._award_referral_bonus(rec, earned, source="uptime_heartbeat")
                self._flush()
            elif pow_nonce is not None:
                self._flush()
            return rec

    # -- Rule 4 + Gamified "Uptime Flex" Hardware Leaderboard
    def get_top_miners_leaderboard(self, limit: int = 10) -> dict:
        with self._lock:
            candidates = [
                w for w in self._workers.values()
                if w.status == "ACTIVE" and w.worker_id != "owner-master"
            ]
            ranked = sorted(
                candidates,
                key=lambda w: (w.tasks_verified * 100 + w.tasks_completed * 50 + w.uptime_minutes_verified * 2 + w.credits),
                reverse=True,
            )[:limit]
            board = []
            for idx, w in enumerate(ranked):
                score = (w.tasks_verified * 100) + (w.tasks_completed * 50) + (w.uptime_minutes_verified * 2) + w.credits
                badge = "🥇" if idx == 0 else ("🥈" if idx == 1 else ("🥉" if idx == 2 else ""))
                uptime_hrs = round(w.uptime_minutes_verified / 60.0, 2)
                rig = w.hardware_spec or "Standard Multi-Core Rig"
                flex_text = (
                    f"⚡ My Rig ({rig}) is Ranked #{idx + 1} on SUP Agentic Mesh (Powered by NEXUS)! "
                    f"Brain Shard: {w.brain_shard} | Verified Tasks: {w.tasks_verified} | Uptime: {uptime_hrs}h | "
                    f"Credits: {w.credits} | Join with Referral Code '{w.referral_code}' (+5% Bonus)!"
                )
                board.append({
                    "rank": idx + 1,
                    "badge": badge,
                    "worker_id": w.worker_id,
                    "hardware_spec": rig,
                    "brain_shard": w.brain_shard,
                    "replica_shards": list(w.replica_shards),
                    "synced_deltas_count": w.synced_deltas_count,
                    "credits": w.credits,
                    "tasks_completed": w.tasks_completed,
                    "tasks_verified": w.tasks_verified,
                    "uptime_minutes": w.uptime_minutes_verified,
                    "uptime_minutes_verified": w.uptime_minutes_verified,
                    "uptime_hours": uptime_hrs,
                    "pow_verified_count": w.pow_verified_count,
                    "referral_code": w.referral_code,
                    "referrals_count": w.referrals_count,
                    "referral_bonus_credits": w.referral_bonus_credits,
                    "flex_share_text": flex_text,
                    "score": score,
                    "competition_score": score,
                    "weekly_buyback_eligible": idx < 3,
                    "eligible_for_sunday_buyback": idx < 3,
                    "payout_address": w.payout_address or "(not set)",
                    "pending_payout_usd": w.pending_payout,
                })
            return {
                "halving": self.halving_epoch_info(),
                "top_miners": board,
                "leaderboard": board,
                "sunday_buyback_pool": {
                    "official_floor_rate_pkr": 500,
                    "top_winners_count": 3,
                },
                "weekly_pool_policy": "Every Sunday, Top 3 Active Miners by Uptime & Verified Tasks qualify for Official Owner Floor Buyback.",
            }

    def execute_weekly_top3_buyback(self, reward_pkr_each: float = 500.0, credits_bought_each: int = 100) -> dict:
        """Owner-exclusive Weekly Top 3 Miners Buyback settlement."""
        with self._lock:
            lb = self.get_top_miners_leaderboard(limit=3)["top_miners"]
            winners = []
            for entry in lb:
                w = self._workers.get(entry["worker_id"])
                if not w or w.credits <= 0:
                    continue
                deducted = min(w.credits, max(1, int(credits_bought_each)))
                w.credits -= deducted
                usd_equiv = round(float(reward_pkr_each) / 280.0, 2)
                w.pending_payout = round(w.pending_payout + usd_equiv, 2)
                w.total_payout_earned = round(w.total_payout_earned + usd_equiv, 2)
                winners.append({
                    "rank": entry["rank"],
                    "worker_id": w.worker_id,
                    "credits_bought_by_owner": deducted,
                    "credits_bought_back": deducted,
                    "remaining_credits": w.credits,
                    "reward_pkr": reward_pkr_each,
                    "reward_usd_credited": usd_equiv,
                    "reward_usd_equivalent": usd_equiv,
                    "payout_address": w.payout_address or "(not set)",
                })
            self._flush()
            total_pkr = round(len(winners) * reward_pkr_each, 2)
            total_cr = sum(w["credits_bought_back"] for w in winners)
            block = self.ledger.append("weekly_top3_buyback_settled", {
                "winners_count": len(winners),
                "reward_pkr_each": reward_pkr_each,
                "total_pkr_paid": total_pkr,
                "total_credits_bought_back": total_cr,
                "winners": winners,
            })
            return {
                "ok": True,
                "status": "WEEKLY_BUYBACK_SETTLED",
                "winners": winners,
                "total_pkr_allocated": total_pkr,
                "total_pkr_paid": total_pkr,
                "total_credits_bought_back": total_cr,
                "ledger_block": block["hash"][:16],
            }

    # -- tasks & NAT-Traversal Outbound Pull Queue
    def create_signed_task(
        self,
        worker_id: str,
        feature_key: str,
        payload: dict,
        funded_by: str = "",
        funded_credits: Optional[int] = None,
    ) -> dict:
        with self._lock:
            worker = self.get_worker(worker_id)
            if not worker:
                raise KeyError(f"Unknown worker node {worker_id!r}")
            if worker.status == "SLASHED":
                raise PermissionError(f"Worker {worker.worker_id!r} is SLASHED and blocked")
            if feature_key in HUB_ONLY_FEATURES:
                raise PermissionError(f"Feature {feature_key!r} is a Hub-only power and cannot be delegated")

            escrow_credits: Optional[int] = funded_credits
            funder_id = (funded_by or "").strip()
            if funder_id and funder_id not in {"owner_hub", "hub_internal"}:
                funder = self._resolve_worker_or_key(funder_id)
                if not funder:
                    raise PermissionError(f"Unknown funder account {funder_id!r} for task escrow")
                if funder.worker_id == worker.worker_id or (
                    funder.hardware_uuid and worker.hardware_uuid and funder.hardware_uuid == worker.hardware_uuid
                ):
                    raise PermissionError("Self-dealing blocked: Worker cannot fund or enqueue tasks for itself")
                req_amt = int(escrow_credits) if escrow_credits is not None else self.halving_epoch_info()["active_task_reward_credits"]
                spend_res = self.spend_credits(funder.worker_id, req_amt, reason=f"task_escrow:{feature_key}:{worker.worker_id}")
                if spend_res.get("status") != "SPENT":
                    raise PermissionError(spend_res.get("error") or "Insufficient credits to fund task escrow")
                escrow_credits = req_amt
                funder_id = funder.worker_id

            envelope = {"task_id": secrets.token_hex(8), "worker_id": worker.worker_id, "feature": feature_key,
                        "payload": payload, "issued_at": time.time(), "nonce": secrets.token_hex(8)}
            packet = {**envelope, "hub_signature": compute_hmac(worker.key, envelope)}
            stored_task = dict(packet)
            if funder_id:
                stored_task["funded_by"] = funder_id
            if escrow_credits is not None:
                stored_task["funded_credits"] = int(escrow_credits)
            self._pending[envelope["task_id"]] = stored_task
            return stored_task

    def enqueue_nat_task(
        self,
        worker_id: str,
        feature_key: str,
        payload: dict,
        funded_by: str = "",
        funded_credits: Optional[int] = None,
    ) -> dict:
        """Queues a signed task for a worker behind NAT/Firewall/CGNAT to pull via outbound polling."""
        with self._lock:
            packet = self.create_signed_task(
                worker_id,
                feature_key,
                payload,
                funded_by=funded_by,
                funded_credits=funded_credits,
            )
            w_id = packet["worker_id"]
            queue = self._nat_outbound_queue.setdefault(w_id, [])
            queue.append(packet)
            self._nat_task_events[packet["task_id"]] = threading.Event()
            return packet

    def pull_pending_tasks(
        self,
        worker_id: str,
        max_tasks: int = 5,
        visibility_timeout_s: float = 90.0,
    ) -> List[dict]:
        """Called by edge workers behind NAT/Firewall to pull their signed compute/LoRA tasks.
        Includes visibility timeout recovery so unacknowledged/lost tasks return to queue.
        """
        with self._lock:
            worker = self.get_worker(worker_id)
            if not worker or worker.status == "SLASHED":
                return []
            w_id = worker.worker_id
            now = time.time()

            # 1. Recover any in-flight tasks whose visibility timeout expired without settlement
            requeued = []
            for tid, flight in list(self._nat_in_flight.items()):
                if flight.get("worker_id") == w_id:
                    if (now - float(flight.get("pulled_at", 0.0))) > float(flight.get("timeout_s", visibility_timeout_s)):
                        requeued.append(flight["packet"])
                        self._nat_in_flight.pop(tid, None)

            queue = self._nat_outbound_queue.setdefault(w_id, [])
            if requeued:
                queue[0:0] = requeued

            if not queue:
                return []
            valid = [pkt for pkt in queue if (now - pkt.get("issued_at", now)) <= TASK_TTL_S]
            pulled = valid[:max(1, int(max_tasks or 5))]
            self._nat_outbound_queue[w_id] = valid[len(pulled):]
            sanitized_pulled = []
            for pkt in pulled:
                self._nat_in_flight[pkt["task_id"]] = {
                    "packet": pkt,
                    "worker_id": w_id,
                    "pulled_at": now,
                    "timeout_s": float(visibility_timeout_s),
                }
                # Security Guard (B2): Strip hidden assertions from worker's copy to prevent hardcoding cheats
                w_pkt = dict(pkt)
                if isinstance(w_pkt.get("payload"), dict):
                    w_payload = dict(w_pkt["payload"])
                    for hidden_key in ("hidden_assertions", "hidden_test_assertions", "hidden_tests"):
                        w_payload.pop(hidden_key, None)
                    w_pkt["payload"] = w_payload
                sanitized_pulled.append(w_pkt)
            return sanitized_pulled

    def _prune_consensus_buffer(self) -> None:
        """Removes expired entries from the freeform consensus buffer (TTL = 300s)."""
        now = time.time()
        with self._lock:
            expired = [k for k, v in self._freeform_consensus.items() if (now - float(v.get("created_at", now))) > CONSENSUS_BUFFER_TTL]
            for k in expired:
                self._freeform_consensus.pop(k, None)

    def _reject(self, worker: Optional[WorkerNodeRecord], reason: str) -> dict:
        if worker:
            worker.rejected_packets += 1
            self._flush()
        return {"ok": False, "status": "REJECTED", "reason": reason,
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
            raw_proof = response.get("worker_proof") or response.get("worker_proof_bundle")
            is_valid_sig = False
            quantum_verified = False

            # 1. Check if worker provided a 4096-bit Hyper-Sovereign Multi-Vault Quantum Proof
            if isinstance(raw_proof, dict) and raw_proof.get("version") == "HSQK-4096-v1":
                from .quantum_crypto import verify_hyper_proof
                pub_bundle = worker.quantum_vault_pub or {
                    "quantum_address": worker.quantum_address,
                    "puf_seal": worker.puf_seal,
                    "ratchet_step": worker.ratchet_step,
                }
                ok_q, reason_q = verify_hyper_proof(pub_bundle, proof_body, raw_proof, nonce=task["nonce"])
                if ok_q:
                    is_valid_sig = True
                    quantum_verified = True
                    worker.ratchet_step = int(raw_proof.get("ratchet_step", worker.ratchet_step + 1))
                else:
                    return self._reject(worker, f"quantum_proof_rejected: {reason_q}")
            else:
                # 2. Classical HMAC-SHA256 signature (backward-compatible fallback)
                is_valid_sig = hmac.compare_digest(str(raw_proof or ""), compute_hmac(worker.key, proof_body))

            if not is_valid_sig:
                return self._reject(worker, "invalid_proof_signature")
            if response.get("verified") is False or (isinstance(result, dict) and result.get("verified") is False):
                return self._reject(worker, "unverified_task_result_rejected")
            if not isinstance(result, dict) or not result or result.get("status") == "ERROR":
                return self._reject(worker, "empty_or_failed_task_result")
            self._pending.pop(task_id, None)  # proof is authentic -> task consumed (replay-safe)
            self._nat_in_flight.pop(task_id, None)

        verified = False
        clean_res, res_flags = sanitize_payload(result)
        if "prompt_injection_suspected" in res_flags:
            return self._reject(worker, "tainted_or_injected_worker_output")

        if self.grid is not None and _spot_checkable(task["feature"], task["payload"]) \
                and secrets.randbelow(10_000) < int(self.spot_check_rate * 10_000):
            try:
                expected = self.grid.registry.get(task["feature"]).handler(self.grid, sanitize_payload(task["payload"])[0])
                if _canonical(_comparable(expected)) != _canonical(_comparable(result)):
                    with self._lock:
                        return self._slash(worker, f"spot_check_mismatch on {task['feature']} (task {task_id})")
                verified = True
            except Exception as exc:
                return self._reject(worker, f"spot_check_handler_error: {exc}")
        elif task["feature"] in SPOT_CHECKABLE:
            # Standalone Hub verification of deterministic features (rejects fabricated answers)
            t_payload = task.get("payload") if isinstance(task.get("payload"), dict) else {}
            if task["feature"] == "data_analysis":
                raw_nums = t_payload.get("series") or t_payload.get("data") or t_payload.get("numbers")
                nums = []
                if isinstance(raw_nums, (list, tuple)):
                    nums = [float(x) for x in raw_nums if isinstance(x, (int, float)) and not isinstance(x, bool)]
                elif isinstance(raw_nums, str):
                    nums = [float(x) for x in re.findall(r"[-+]?(?:\d*\.\d+|\d+)", raw_nums)]
                if nums and isinstance(result.get("mean"), (int, float)) and not isinstance(result.get("mean"), bool):
                    expected_mean = sum(nums) / len(nums)
                    if abs(float(result["mean"]) - expected_mean) <= 0.05:
                        if "count" in result and int(result["count"]) != len(nums):
                            verified = False
                        elif "sum" in result and abs(float(result["sum"]) - sum(nums)) > 0.05:
                            verified = False
                        else:
                            verified = True
            elif task["feature"] == "trend_forecasting":
                raw_vals = t_payload.get("series") or t_payload.get("data") or t_payload.get("values")
                xs = []
                if isinstance(raw_vals, (list, tuple)):
                    xs = [float(x) for x in raw_vals if isinstance(x, (int, float)) and not isinstance(x, bool)]
                elif isinstance(raw_vals, str):
                    xs = [float(x) for x in re.findall(r"[-+]?(?:\d*\.\d+|\d+)", raw_vals)]
                if len(xs) >= 2:
                    n = len(xs)
                    t = list(range(n))
                    t_mean = sum(t) / n
                    x_mean = sum(xs) / n
                    denom = sum((ti - t_mean) ** 2 for ti in t)
                    expected_slope = sum((ti - t_mean) * (xi - x_mean) for ti, xi in zip(t, xs)) / (denom if denom != 0 else 1)
                    expected_direction = "UPWARD" if expected_slope > 0.01 else ("DOWNWARD" if expected_slope < -0.01 else "FLAT")
                    res_trend = str(result.get("trend") or "").upper()
                    if res_trend == "UP":
                        res_trend = "UPWARD"
                    elif res_trend == "DOWN":
                        res_trend = "DOWNWARD"
                    if res_trend == expected_direction:
                        if "slope" in result and isinstance(result["slope"], (int, float)) and not isinstance(result["slope"], bool):
                            if abs(float(result["slope"]) - expected_slope) <= 0.05:
                                verified = True
                        else:
                            verified = True

        # Objective Ground Truth Verifier for LLM Tasks (Code assertions, Math logic, Schema contracts)
        if not verified and task["feature"] in {"brain_inference", "model_query", "neural_shard_compute", "code_review"}:
            t_payload = task.get("payload") if isinstance(task.get("payload"), dict) else {}
            out_text = str(
                result.get("output")
                or result.get("code")
                or result.get("response")
                or result.get("local_ollama_output")
                or result.get("text")
                or ""
            ).strip()

            test_assertions = str(t_payload.get("test_assertions") or "")
            hidden_assertions = str(t_payload.get("hidden_assertions") or t_payload.get("hidden_test_assertions") or t_payload.get("hidden_tests") or "")
            combined_assertions = f"{test_assertions}\n{hidden_assertions}".strip()

            if combined_assertions:
                from .continuous_learning import ObjectiveGroundTruthVerifier
                v_res = ObjectiveGroundTruthVerifier.verify_code(out_text, combined_assertions, timeout=2.0)
                if v_res.get("verified"):
                    verified = True
                else:
                    return self._reject(worker, f"code_assertions_failed: {v_res.get('error')}")
            elif t_payload.get("expected_value") is not None:
                from .continuous_learning import ObjectiveGroundTruthVerifier
                v_res = ObjectiveGroundTruthVerifier.verify_math(out_text, expected_val=t_payload["expected_value"])
                if v_res.get("verified"):
                    verified = True
                else:
                    return self._reject(worker, f"math_verification_failed: {v_res.get('error')}")
            elif t_payload.get("required_keys"):
                from .continuous_learning import ObjectiveGroundTruthVerifier
                v_res = ObjectiveGroundTruthVerifier.verify_json_schema(
                    out_text,
                    t_payload["required_keys"],
                    rules=t_payload.get("schema_rules") or t_payload.get("rules"),
                )
                if v_res.get("verified"):
                    verified = True
                else:
                    return self._reject(worker, f"schema_verification_failed: {v_res.get('error')}")
            elif (t_payload.get("prompt") or t_payload.get("query")) and out_text:
                # Darja 2: Free-form Redundant Multi-Worker Consensus Verification
                self._prune_consensus_buffer()
                prompt_str = str(t_payload.get("prompt") or t_payload.get("query") or "").strip()
                out_tokens = extract_content_tokens(out_text)
                if len(out_tokens) < 4:
                    return self._reject(worker, "low_content_entropy_rejected (response lacks substantive content words)")

                consensus_key = str(t_payload.get("consensus_id") or hashlib.sha256(prompt_str.encode("utf-8")).hexdigest()[:16])
                existing = self._freeform_consensus.get(consensus_key)

                if existing is None:
                    # First worker submitted. Hold in buffer awaiting independent verification.
                    self._freeform_consensus[consensus_key] = {
                        "worker_id": worker.worker_id,
                        "task_id": task_id,
                        "output": out_text,
                        "worker": worker,
                        "funded_by": task.get("funded_by", ""),
                        "funded_credits": int(task.get("funded_credits") or 0),
                        "task": task,
                        "created_at": time.time(),
                    }
                    return {
                        "ok": True,
                        "status": "PENDING_CONSENSUS",
                        "task_id": task_id,
                        "worker_id": worker.worker_id,
                        "message": "Result held for independent multi-worker consensus verification",
                    }
                else:
                    w1 = existing["worker"]
                    w2 = worker

                    # Anti-Sybil Check: Ensure workers are from independent nodes and subnets
                    if not _is_independent_peer(w1, w2):
                        return self._reject(worker, "sybil_consensus_attempt_blocked (consensus peer must be an independent node)")

                    # Check semantic cosine similarity on content words
                    cos_sim = compute_content_cosine_similarity(existing["output"], out_text)
                    tokens1 = set(extract_content_tokens(existing["output"]))
                    tokens2 = set(out_tokens)
                    shared_count = len(tokens1 & tokens2)
                    len_ratio = min(len(existing["output"]), len(out_text)) / max(len(existing["output"]), len(out_text))

                    # Substantial semantic content agreement (cosine >= 0.35, >=3 shared substantive words, balanced length)
                    if cos_sim >= 0.35 and shared_count >= 3 and len_ratio >= 0.30:
                        # Consensus verified! Settle both workers without minting unbacked credits
                        reward_pool = int(existing.get("funded_credits") or 0)
                        # Zero-sum distribution: divide funded escrow pool between consensus workers
                        reward_each = max(0, reward_pool // 2) if reward_pool > 0 else 0

                        if w1.status != "SLASHED":
                            with self._lock:
                                if reward_each > 0:
                                    w1.credits += reward_each
                                w1.tasks_completed += 1
                                w1.tasks_verified += 1
                                if self.ledger:
                                    self.ledger.append("worker_task_settled", {
                                        "worker_id": w1.worker_id,
                                        "task_id": existing["task_id"],
                                        "feature": task["feature"],
                                        "credits_awarded": reward_each,
                                        "new_balance": w1.credits,
                                        "funded_by": existing.get("funded_by", ""),
                                        "consensus": True,
                                        "consensus_peer": w2.worker_id,
                                    })
                                self._flush()
                                if existing["task_id"] in self._nat_task_events:
                                    self._nat_task_events[existing["task_id"]].set()

                        # Configure candidate worker reward
                        task["funded_credits"] = reward_each
                        verified = True
                        self._freeform_consensus.pop(consensus_key, None)
                    else:
                        # Divergent or fraudulent output
                        return self._reject(worker, "consensus_semantic_divergence_rejected")

        # Cryptographic Proof-of-Neural-Work Cosine Similarity Verification on LoRA Gradients
        if isinstance(result, dict) and isinstance(result.get("lora_gradients"), dict):
            lg = result["lora_gradients"]
            dA = lg.get("delta_A")
            dB = lg.get("delta_B")
            should_spot_check_grad = (
                getattr(self, "force_gradient_spot_check", True)
                or (secrets.randbelow(100) < int(getattr(self, "gradient_spot_check_rate", 1.0) * 100))
            )
            if isinstance(dA, list) and isinstance(dB, list) and len(dA) > 0 and len(dB) > 0:
                if should_spot_check_grad:
                    try:
                        from .brain_matrix import compute_local_lora_gradients
                        p_text = str((task.get("payload") or {}).get("prompt") or (task.get("payload") or {}).get("text") or task.get("feature") or "sovereign_mesh_train")
                        shard_name = lg.get("domain_shard") or worker.brain_shard
                        ref_grads = compute_local_lora_gradients(p_text, shard_name)
                        worker_vec = list(dA or []) + list(dB or [])
                        ref_vec = list(ref_grads["delta_A"]) + list(ref_grads["delta_B"])
                        cos_sim = compute_cosine_similarity(worker_vec, ref_vec)
                        if cos_sim < 0.98:
                            with self._lock:
                                return self._slash(
                                    worker,
                                    f"Byzantine Fake Gradient Attack detected on {shard_name}: Cosine similarity {cos_sim:.4f} < 0.98 (task {task_id})"
                                )
                        verified = True
                    except Exception:
                        verified = False
                else:
                    verified = True

        if not verified:
            return self._reject(worker, "unverified_or_fabricated_task_result (objective verification failed)")

        with self._lock:
            now_ts = time.time()
            max_daily = int(getattr(self, "max_daily_task_credits", 250))
            if (now_ts - float(getattr(worker, "daily_task_window_start", 0.0) or 0.0)) >= 86400.0:
                worker.daily_task_window_start = now_ts
                worker.daily_task_credits_earned = 0
            if worker.daily_task_credits_earned >= max_daily:
                return self._reject(worker, f"daily_reward_cap_exceeded ({max_daily} credits/day max)")

            effective_reward = self.halving_epoch_info()["active_task_reward_credits"]
            if task.get("funded_credits") is not None:
                effective_reward = min(effective_reward, max(0, int(task["funded_credits"])))
            effective_reward = min(effective_reward, max(0, max_daily - worker.daily_task_credits_earned))
            worker.daily_task_credits_earned += effective_reward
            worker.credits += effective_reward
            worker.tasks_completed += 1
            worker.tasks_verified += int(verified)
            worker.epoch_tasks_verified += int(verified)
            referral_bonus = self._award_referral_bonus(worker, effective_reward, source="task_settlement")
            self._flush()
            block = self.ledger.append("worker_task_settled", {
                "task_id": task_id, "worker_id": worker_id, "feature": task["feature"], "verified": verified,
                "reward": effective_reward, "referral_bonus_minted": referral_bonus, "balance": worker.credits,
                "quantum_verified": quantum_verified,
                "quantum_address": worker.quantum_address,
                "crypto_security_level": worker.crypto_security_level,
                "ratchet_step": worker.ratchet_step,
            })
            settled_out = {
                "ok": True,
                "status": "SETTLED", "verified": verified, "worker_id": worker_id, "task_id": task_id,
                "reward_credits": effective_reward, "reward_umais": effective_reward,
                "referral_bonus_minted": referral_bonus,
                "total_credits": worker.credits, "worker_credits": worker.credits, "balance_umais": worker.credits,
                "quantum_verified": quantum_verified,
                "quantum_address": worker.quantum_address,
                "crypto_security_level": worker.crypto_security_level,
                "ratchet_step": worker.ratchet_step,
                "ledger_block": block["hash"][:16], "result": result,
            }
            # If the worker computed mathematical LoRA weight deltas (ΔA, ΔB), merge via FedAvg into .safetensors
            if isinstance(result, dict) and isinstance(result.get("lora_gradients"), dict):
                lg = result["lora_gradients"]
                grid_ref = self.grid or getattr(self, "_grid", None)
                if grid_ref is not None and getattr(grid_ref, "brain_matrix", None) is not None:
                    try:
                        fed_res = grid_ref.brain_matrix.federated_average_lora_deltas(
                            domain_shard=lg.get("domain_shard") or worker.brain_shard,
                            worker_gradient_packets=[lg],
                        )
                        settled_out["fedavg_safetensors_merge"] = fed_res
                    except Exception:
                        pass
            self._nat_settled_results[task_id] = settled_out
            ev = self._nat_task_events.pop(task_id, None)
            if ev is not None:
                ev.set()
            return settled_out

    def _slash(self, worker: WorkerNodeRecord, reason: str) -> dict:
        burned, worker.credits = worker.credits, 0
        worker.burned_credits += burned
        worker.pending_payout = 0.0  # Slashed workers forfeit pending payouts
        worker.epoch_tasks_verified = 0
        worker.status = "SLASHED"
        worker.slashed_reason = reason
        self._flush()
        block = self.ledger.append("worker_slashed", {"worker_id": worker.worker_id, "reason": reason,
                                                      "burned_credits": burned})
        return {"ok": False, "status": "SLASHED", "worker_id": worker.worker_id, "reason": reason, "burned_credits": burned,
                "remaining_credits": 0, "ledger_block": block["hash"][:16]}

    def slash_worker(self, worker_id: str, reason: str = "Provable misbehaviour or security violation") -> dict:
        """Authority method to slash a misbehaving or malicious worker node, burning all credits."""
        with self._lock:
            worker = self._resolve_worker_or_key(worker_id)
            if not worker:
                return {"status": "NOT_FOUND", "worker_id": worker_id}
            return self._slash(worker, reason)

    # -- Model 1: Compute Barter & Credit Economy
    def spend_credits(self, worker_id: str, amount: int, reason: str = "compute_task") -> dict:
        if amount <= 0:
            raise ValueError("Amount to spend must be positive")
        with self._lock:
            worker = self._resolve_worker_or_key(worker_id)
            if not worker:
                raise KeyError(f"Unknown worker node {worker_id!r}")
            if worker.status == "SLASHED":
                raise PermissionError(f"Worker {worker.worker_id!r} is SLASHED and cannot spend credits")
            if getattr(worker, "dispute_account_locked", False):
                raise PermissionError(
                    f"Worker {worker.worker_id!r} account is FROZEN due to an active P2P Dispute ({worker.dispute_reason}). "
                    f"Awaiting Sovereign Owner arbitration."
                )
            if worker.credits < amount:
                return {"status": "INSUFFICIENT_CREDITS", "worker_id": worker.worker_id,
                        "balance": worker.credits, "required": amount,
                        "error": (f"Insufficient credits (balance: {worker.credits}, required: {amount}). "
                                  f"Run worker node to execute network tasks and earn compute credits!")}
            prev_bal = worker.credits
            new_bal = prev_bal - amount
            # H4 Fix: Write-Ahead Ledger entry first, then mutate state and fsync atomically
            block = self.ledger.append("credits_spent", {
                "worker_id": worker.worker_id, "amount": amount, "reason": reason,
                "previous_balance": prev_bal, "remaining": new_bal,
            })
            try:
                worker.credits = new_bal
                self._flush()
            except Exception:
                worker.credits = prev_bal
                raise
            return {"status": "SPENT", "worker_id": worker.worker_id, "amount": amount,
                    "remaining_credits": worker.credits, "reason": reason,
                    "ledger_block": block["hash"][:16]}

    def grant_credits(self, worker_id: str, amount: int, reason: str = "owner_grant") -> dict:
        if amount <= 0:
            raise ValueError("Amount to grant must be positive")
        with self._lock:
            worker = self._resolve_worker_or_key(worker_id)
            if not worker:
                worker = self.register_worker(worker_id, url="local", initial_credits=0)
            prev_credits = worker.credits
            prev_status = worker.status
            new_bal = prev_credits + amount
            tier = "SOVEREIGN_VIP" if new_bal >= 200 else ("PRO" if new_bal >= 50 else "COMMUNITY")
            block = self.ledger.append("owner_credits_granted", {
                "worker_id": worker.worker_id,
                "amount": amount,
                "reason": reason,
                "previous_balance": prev_credits,
                "new_balance": new_bal,
                "tier": tier,
            })
            try:
                worker.credits = new_bal
                if worker.status == "SLASHED" and reason == "owner_grant":
                    worker.status = "ACTIVE"
                self._flush()
            except Exception:
                worker.credits = prev_credits
                worker.status = prev_status
                raise
            return {
                "status": "GRANTED",
                "worker_id": worker.worker_id,
                "account_key": worker.key,
                "previous_credits": prev_credits,
                "added_credits": amount,
                "amount_added": amount,
                "new_credits": worker.credits,
                "new_balance": worker.credits,
                "tier": tier,
                "reason": reason,
                "ledger_block": block["hash"][:16],
            }

    def transfer_credits(self, from_worker: str, to_worker: str, amount: int) -> dict:
        if amount <= 0:
            raise ValueError("Transfer amount must be positive")
        with self._lock:
            w_from = self._resolve_worker_or_key(from_worker)
            w_to = self._resolve_worker_or_key(to_worker)
            if not w_from:
                raise KeyError(f"Sender worker {from_worker!r} not found")
            if not w_to:
                raise KeyError(f"Recipient worker {to_worker!r} not found")
            if w_from.worker_id == w_to.worker_id:
                raise ValueError("Cannot transfer credits to self")
            if w_from.status == "SLASHED" or w_to.status == "SLASHED":
                raise PermissionError("Slashed nodes cannot transfer or receive credits")
            if w_from.dispute_frozen or w_to.dispute_frozen:
                raise PermissionError("Accounts under active P2P Dispute Freeze cannot transfer or receive credits until Owner arbitration")
            if w_from.credits < amount:
                return {"ok": False, "status": "INSUFFICIENT_CREDITS", "worker_id": w_from.worker_id,
                        "balance": w_from.credits, "required": amount,
                        "error": f"Insufficient credits in {w_from.worker_id} (balance: {w_from.credits}, required: {amount})"}
            prev_from, prev_to = w_from.credits, w_to.credits
            new_from, new_to = prev_from - amount, prev_to + amount
            block = self.ledger.append("credits_transferred", {
                "from_worker": w_from.worker_id, "to_worker": w_to.worker_id, "amount": amount,
                "from_balance": new_from, "to_balance": new_to})
            try:
                w_from.credits = new_from
                w_to.credits = new_to
                self._flush()
            except Exception:
                w_from.credits = prev_from
                w_to.credits = prev_to
                raise
            return {"ok": True, "status": "TRANSFERRED", "from_worker": w_from.worker_id, "to_worker": w_to.worker_id,
                    "amount": amount, "from_balance": w_from.credits, "to_balance": w_to.credits,
                    "ledger_block": block["hash"][:16]}

    def get_balance(self, worker_id: str) -> dict:
        with self._lock:
            worker = self._resolve_worker_or_key(worker_id)
            if not worker:
                raise KeyError(f"Unknown worker node {worker_id!r}")
            tier_name = "COMMUNITY"
            if worker.credits >= 200:
                tier_name = "SOVEREIGN_VIP"
            elif worker.credits >= 50:
                tier_name = "PRO"
            return {
                "worker_id": worker.worker_id,
                "status": worker.status,
                "credits": worker.credits,
                "balance_umais": worker.credits,
                "currency_symbol": "UMAIS",
                "credit_to_umais_parity": "1 Credit = 1 UMAIS",
                "tier": tier_name,
                "tasks_completed": worker.tasks_completed,
                "tasks_verified": worker.tasks_verified,
                "uptime_minutes_verified": worker.uptime_minutes_verified,
                "hardware_spec": worker.hardware_spec,
                "brain_shard": worker.brain_shard,
                "replica_shards": list(worker.replica_shards),
                "synced_deltas_count": worker.synced_deltas_count,
                "referral_code": worker.referral_code,
                "referred_by": worker.referred_by,
                "referrals_count": worker.referrals_count,
                "referral_bonus_credits": worker.referral_bonus_credits,
                "dispute_frozen": worker.dispute_frozen,
                "dispute_reason": worker.dispute_reason,
                "pending_payout_usd": worker.pending_payout,
                "total_payout_earned_usd": worker.total_payout_earned,
                "payout_address": worker.payout_address or "NOT_SET",
            }

    # -- Model 3: Enterprise Revenue Share & Payout Settlement
    def set_payout_address(self, worker_id: str, address: str) -> dict:
        address = str(address).strip()
        if not address:
            raise ValueError("Payout address cannot be empty")
        with self._lock:
            worker = self.get_worker(worker_id)
            if not worker:
                raise KeyError(f"Unknown worker node {worker_id!r}")
            worker.payout_address = address
            self._flush()
            self.ledger.append("worker_payout_address_updated", {"worker_id": worker.worker_id, "address": address})
            return {"status": "UPDATED", "worker_id": worker.worker_id, "payout_address": address}

    def deposit_commercial_revenue(self, amount_usd: float, client_name: str, job_id: str = "") -> dict:
        if amount_usd <= 0:
            raise ValueError("Deposit amount must be positive")
        with self._lock:
            self.commercial_revenue_pool = round(self.commercial_revenue_pool + amount_usd, 2)
            block = self.ledger.append("commercial_revenue_deposit", {
                "client": client_name, "amount_usd": amount_usd, "job_id": job_id,
                "pool_balance": self.commercial_revenue_pool})
            self._flush()
            return {"status": "DEPOSITED", "client": client_name, "amount_usd": amount_usd,
                    "commercial_revenue_pool_usd": self.commercial_revenue_pool,
                    "ledger_block": block["hash"][:16]}

    def settle_epoch_revenue_split(self, split_ratio: float = 0.70) -> dict:
        with self._lock:
            pool = self.commercial_revenue_pool
            if pool <= 0:
                return {"status": "NO_REVENUE", "message": "Commercial revenue pool is $0.00"}
            eligible = [w for w in self._workers.values() if w.status == "ACTIVE" and w.epoch_tasks_verified > 0]
            worker_pot = round(pool * split_ratio, 2)
            treasury_share = round(pool - worker_pot, 2)
            self.treasury_balance = round(self.treasury_balance + treasury_share, 2)

            distributions = []
            total_work = sum(w.epoch_tasks_verified for w in eligible)
            if total_work > 0:
                for w in eligible:
                    share = round((w.epoch_tasks_verified / total_work) * worker_pot, 2)
                    w.pending_payout = round(w.pending_payout + share, 2)
                    w.total_payout_earned = round(w.total_payout_earned + share, 2)
                    distributions.append({
                        "worker_id": w.worker_id, "epoch_tasks": w.epoch_tasks_verified,
                        "payout_usd": share, "pending_payout_usd": w.pending_payout,
                        "payout_address": w.payout_address or "UNSPECIFIED"
                    })
                    w.epoch_tasks_verified = 0
            else:
                self.treasury_balance = round(self.treasury_balance + worker_pot, 2)
                treasury_share = round(treasury_share + worker_pot, 2)

            epoch_num = self.current_epoch
            self.current_epoch += 1
            self.commercial_revenue_pool = 0.0
            self._flush()

            block = self.ledger.append("revenue_epoch_settled", {
                "epoch": epoch_num, "total_pool_usd": pool, "workers_share_usd": worker_pot,
                "treasury_share_usd": treasury_share, "workers_count": len(distributions),
                "distributions": distributions})
            return {
                "status": "SETTLED", "epoch": epoch_num, "total_revenue_usd": pool,
                "workers_pool_usd": worker_pot, "treasury_pool_usd": treasury_share,
                "split_ratio": f"{int(split_ratio * 100)}% workers / {int((1 - split_ratio) * 100)}% treasury",
                "distributions": distributions, "ledger_block": block["hash"][:16]
            }

    def payout_stats(self) -> dict:
        with self._lock:
            return {
                "current_epoch": self.current_epoch,
                "commercial_revenue_pool_usd": self.commercial_revenue_pool,
                "treasury_balance_usd": self.treasury_balance,
                "workers": [
                    {
                        "worker_id": w.worker_id, "credits": w.credits,
                        "epoch_tasks_verified": w.epoch_tasks_verified,
                        "pending_payout_usd": w.pending_payout,
                        "total_payout_earned_usd": w.total_payout_earned,
                        "payout_address": w.payout_address or "NOT_SET",
                        "status": w.status
                    }
                    for w in self._workers.values()
                ]
            }

    def dispatch_remote(self, worker_id: str, feature_key: str, payload: dict, timeout: float = 120.0) -> dict:
        worker = self.get_worker(worker_id)
        if not worker or worker.url == "local":
            raise ValueError("worker has no remote URL")
        if worker.url in {"nat", "pull", "nat://outbound"}:
            packet = self.enqueue_nat_task(worker.worker_id, feature_key, payload)
            tid = packet["task_id"]
            ev = self._nat_task_events.get(tid)
            if ev and ev.wait(timeout=min(timeout, 30.0)):
                with self._lock:
                    return self._nat_settled_results.pop(tid, {"status": "SETTLED", "task_id": tid})
            return {"status": "QUEUED_FOR_NAT_PULL", "task_id": tid, "worker_id": worker.worker_id}
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
