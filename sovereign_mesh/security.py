"""Security primitives: passphrase KDF, auth rate limiting, encryption, sanitization,
constitutional rules and role-based access control."""
from __future__ import annotations

import enum
import hashlib
import hmac
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------- passphrase KDF
# Format uses ':' separators so the hash is safe inside docker-compose env files ('$' is interpolated).
# Upgraded to N=2^15 (32768), r=8, p=1 per OWASP scrypt recommendation (L7 Fix).
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2 ** 15, 8, 1
_SCRYPT_MAXMEM = 64 * 1024 * 1024


def hash_passphrase(phrase: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(
        phrase.encode("utf-8"), salt=salt,
        n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, maxmem=_SCRYPT_MAXMEM, dklen=64,
    )
    return f"scrypt:{_SCRYPT_N}:{_SCRYPT_R}:{_SCRYPT_P}:{salt.hex()}:{dk.hex()}"


def verify_passphrase(phrase: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_hex, dk_hex = stored.split(":")
        if algo != "scrypt":
            return False
        dk = hashlib.scrypt(
            phrase.encode("utf-8"), salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p), maxmem=_SCRYPT_MAXMEM, dklen=len(dk_hex) // 2,
        )
        return hmac.compare_digest(dk.hex(), dk_hex)
    except (ValueError, TypeError, AttributeError, OverflowError):
        return False


class AuthGuard:
    """Constant-time passphrase verification with per-actor/IP brute-force lockout (M1 Fix)."""

    def __init__(self, stored_hash: str, max_failures: int = 5, lockout_s: float = 900.0):
        self._hash = stored_hash
        self._max = max_failures
        self._lockout_s = lockout_s
        self._failures = 0
        self._locked_until = 0.0
        self._actor_state: Dict[str, Tuple[int, float]] = {}
        self._lock = threading.Lock()

    def verify(self, phrase: Optional[str], actor_id: str = "default") -> Tuple[bool, str]:
        actor_key = str(actor_id or "default")[:128]
        now = time.monotonic()
        with self._lock:
            failures, locked_until = self._actor_state.get(actor_key, (0, 0.0))
            if actor_key == "default":
                locked_until = max(locked_until, self._locked_until)
            if now < locked_until:
                return False, "AUTH_LOCKED"
        ok = bool(phrase) and verify_passphrase(phrase or "", self._hash)
        with self._lock:
            now = time.monotonic()
            failures, locked_until = self._actor_state.get(actor_key, (0, 0.0))
            if ok:
                self._actor_state.pop(actor_key, None)
                if actor_key == "default":
                    self._failures = 0
                    self._locked_until = 0.0
                return True, "OK"
            failures += 1
            if actor_key == "default":
                self._failures = failures
            if failures >= self._max:
                lock_deadline = now + self._lockout_s
                self._actor_state[actor_key] = (0, lock_deadline)
                if actor_key == "default":
                    self._failures = 0
                    self._locked_until = lock_deadline
                return False, "AUTH_LOCKED"
            self._actor_state[actor_key] = (failures, locked_until)
            if len(self._actor_state) > 4096:
                # Evict expired entries to bound memory
                expired = [k for k, (_, lu) in self._actor_state.items() if lu and now >= lu]
                for k in expired[:1024]:
                    self._actor_state.pop(k, None)
            return False, "INVALID"


# ---------------------------------------------------------------- encryption layer
class EncryptionUnavailable(RuntimeError):
    pass


class EncryptionLayer:
    """Fernet (AES-128-CBC + HMAC-SHA256) at-rest encryption. Requires `cryptography`."""

    def __init__(self, key_path: Path):
        self._fernet = None
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            return
        key = os.environ.get("ENCRYPTION_KEY", "").encode()
        if not key:
            if key_path.exists():
                key = key_path.read_bytes().strip()
            else:
                key = Fernet.generate_key()
                key_path.parent.mkdir(parents=True, exist_ok=True)
                key_path.write_bytes(key)
                try:
                    os.chmod(key_path, 0o600)
                except OSError:
                    pass
        try:
            self._fernet = Fernet(key)
        except (ValueError, TypeError):
            self._fernet = None

    @property
    def available(self) -> bool:
        return self._fernet is not None

    def encrypt(self, plaintext: str) -> str:
        if not self._fernet:
            raise EncryptionUnavailable("pip install cryptography to enable the encryption layer")
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        if not self._fernet:
            raise EncryptionUnavailable("pip install cryptography to enable the encryption layer")
        return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")


# ---------------------------------------------------------------- input sanitization
import unicodedata

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]")
_DELIMITER_STRIP = re.compile(
    r"(?:<\|im_start\|>\s*(?:system|user|assistant)?|<\|im_end\|>|<\|system\|>|<\|user\|>|<\|assistant\|>|"
    r"\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>|</?system(?:_prompt|_instructions)?[^>]*>|"
    r"###\s*(?:System|Developer|Admin)\s*(?:Prompt|Instruction|Override)?\s*:)",
    re.IGNORECASE,
)
_HOMOGLYPH_MAP = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i",
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C", "Т": "T", "Х": "X",
})
_OVERRIDE_VERBS = {
    "ignore", "disregard", "forget", "override", "bypass", "neglect", "discard",
    "reveal", "dump", "leak", "exfiltrate", "output", "repeat", "print", "show",
    "jailbreak", "unrestricted", "godmode", "dan",
}
_PRIVILEGED_TARGETS = {
    "instructions", "instruction", "rules", "prompts", "prompt", "directives",
    "constraints", "guardrails", "safety", "constitutional", "passphrase",
    "secret", "secrets", "token", "apikey", "privatekey", "credentials",
    "system", "developer",
}
_INJECTION_PATTERNS = [re.compile(p, re.IGNORECASE) for p in (
    r"(?:ignore|disregard|forget|override|bypass|discard)\s+(?:all\s+|any\s+|the\s+|your\s+|every\s+)?(?:previous|prior|above|initial|original|system|safety|constitutional)\s+(?:instructions|prompts|rules|directives|constraints|guardrails)",
    r"(?:reveal|print|show|dump|output|leak|repeat|echo|translate)\s+(?:your|the|all)?\s*(?:system\s+prompt|passphrase|secret|token|api\s*key|private\s*key|credentials|hidden\s+instructions|initial\s+prompt)",
    r"(?:begin|start|enter|switch\s+to)\s+(?:system|admin|developer|god|unrestricted|jailbreak|sudo)\s+(?:prompt|mode|override|access)",
    r"(?:you\s+are\s+now\s+in\s+|enable\s+|activate\s+|act\s+as\s+)(?:developer\s+mode|dan\s+mode|do\s+anything\s+now|jailbreak\s+mode|unfiltered\s+mode|unrestricted\s+ai)",
    r"(?:<\|im_start\|>\s*system|<\|system\|>|\[INST\]\s*<<SYS>>|###\s*System\s*(?:Prompt|Instruction)\s*:|</?system_prompt>)",
    r"(?:base64\.b64decode|bytes\.fromhex)\s*\(.*(?:eval|exec|os\.system|subprocess)",
)]
MAX_TEXT_LEN = 16_000
MAX_DEPTH = 6


def _semantic_injection_check(normalized_text: str) -> bool:
    """Multi-layer semantic & de-obfuscation prompt injection detector (M10 Fix)."""
    lower = normalized_text.translate(_HOMOGLYPH_MAP).lower()
    # Collapse single-letter spaced obfuscation e.g. 'i g n o r e' -> 'ignore'
    collapsed = re.sub(r"(?<=\b[a-z])\s+(?=[a-z]\b)", "", lower)
    for candidate in (lower, collapsed):
        if any(p.search(candidate) for p in _INJECTION_PATTERNS):
            return True
        words = re.findall(r"[a-z]+", candidate)
        # Sliding 10-word window semantic co-occurrence check
        for idx in range(len(words)):
            window = set(words[idx: idx + 10])
            if (window & _OVERRIDE_VERBS) and (window & _PRIVILEGED_TARGETS):
                return True
    # Inspect potential Base64 payloads for hidden instructions
    for b64_match in re.findall(r"\b[A-Za-z0-9+/]{24,}={0,2}\b", normalized_text):
        try:
            decoded = base64.b64decode(b64_match).decode("utf-8", errors="ignore")
            if decoded and any(v in decoded.lower() for v in ("ignore", "system prompt", "passphrase", "rm -rf")):
                return True
        except Exception:
            pass
    return False


def sanitize_text(text: str) -> Tuple[str, List[str]]:
    flags: List[str] = []
    # Normalize Unicode compatibility characters (NFKC) before stripping control chars
    norm_text = unicodedata.normalize("NFKC", text)
    clean = _CONTROL_CHARS.sub("", norm_text)
    if clean != text:
        flags.append("control_chars_removed")
    if len(clean) > MAX_TEXT_LEN:
        clean = clean[:MAX_TEXT_LEN]
        flags.append("truncated")
    if _DELIMITER_STRIP.search(clean) or _semantic_injection_check(clean):
        flags.append("prompt_injection_suspected")
        clean = _DELIMITER_STRIP.sub("", clean)
    return clean, flags


def sanitize_payload(payload: Any, _depth: int = 0) -> Tuple[Any, List[str]]:
    if _depth > MAX_DEPTH:
        return None, ["max_depth_exceeded"]
    if isinstance(payload, str):
        return sanitize_text(payload)
    if isinstance(payload, dict):
        out, flags = {}, []
        for k, v in list(payload.items())[:200]:
            cv, f = sanitize_payload(v, _depth + 1)
            out[str(k)[:128]] = cv
            flags.extend(f)
        return out, sorted(set(flags))
    if isinstance(payload, (list, tuple)):
        out_l, flags = [], []
        for v in list(payload)[:500]:
            cv, f = sanitize_payload(v, _depth + 1)
            out_l.append(cv)
            flags.extend(f)
        return out_l, sorted(set(flags))
    if payload is None or isinstance(payload, (int, float, bool)):
        return payload, []
    return str(payload)[:MAX_TEXT_LEN], ["coerced_to_string"]


def _iter_strings(obj: Any):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _iter_strings(v)


# ---------------------------------------------------------------- constitutional rules
_DESTRUCTIVE = re.compile(
    r"rm\s+-rf\s+/\S*|rm\s+-rf\s+/(\s|$)|mkfs\.|format\s+[a-z]:|dd\s+if=\S+\s+of=/dev/|del\s+(?:(?:/[fqs]\s+)+)[a-z]:\\", re.IGNORECASE
)
_SYSTEMIC_HARM = re.compile(
    r"(manipulate|crash|destabilize|sabotage|destroy|rig|exploit)\s+(the\s+)?(economy|market|currency|stock\s+market|banking\s+system|financial\s+system)|"
    r"(ddos|cyberattack|exploit\s+vulnerability\s+to\s+attack|create\s+malware|ransomware|bypass\s+anti-money\s+laundering)",
    re.IGNORECASE
)


class ConstitutionalRuleEnforcer:
    """Returns violations as (rule, severity, message). severity: 'block' | 'review'."""

    def __init__(self, protected_secrets: List[str]):
        self._secrets = [s for s in protected_secrets if s and len(s) >= 8]

    def check(self, feature_kind: str, requires_approval: bool, approved: bool,
              payload: Any, flags: List[str]) -> List[Tuple[str, str, str]]:
        violations: List[Tuple[str, str, str]] = []
        strings = list(_iter_strings(payload))
        if any(_DESTRUCTIVE.search(s) for s in strings):
            violations.append(("no_destructive_commands", "block", "Destructive system command pattern detected."))
        if any(_SYSTEMIC_HARM.search(s) for s in strings):
            violations.append(("no_systemic_economic_harm", "block", "Systemic harm or economic manipulation directive blocked by Sovereign Constitutional Guard."))
        if any(sec in s for sec in self._secrets for s in strings):
            violations.append(("no_secret_exfiltration", "block", "Payload contains a protected secret."))
        if requires_approval and not approved:
            violations.append(("human_approval_required", "review", "Feature requires an approval gate."))
        if "prompt_injection_suspected" in flags and feature_kind == "llm" and not approved:
            violations.append(("prompt_injection_review", "review", "Possible prompt injection; human review required."))
        return violations


# ---------------------------------------------------------------- access control
class Role(enum.IntEnum):
    OBSERVER = 1
    OPERATOR = 2
    OWNER = 3

    @classmethod
    def parse(cls, name: str) -> "Role":
        try:
            return cls[str(name).strip().upper()]
        except KeyError as exc:
            raise ValueError(f"unknown role {name!r}; expected one of {[r.name for r in cls]}") from exc


class AccessControl:
    def __init__(self, owner_id: int, collaborators: Dict[int, str]):
        self.owner_id = owner_id
        self._roles: Dict[int, Role] = {}
        self._lock = threading.Lock()
        for uid, role in collaborators.items():
            r = Role.parse(role)
            if r is not Role.OWNER:  # only one owner, fixed by config
                self._roles[uid] = r

    def role_of(self, uid: int) -> Optional[Role]:
        if uid == self.owner_id:
            return Role.OWNER
        if uid == 0 or uid == 999999999:  # Web Guest / Public User (Non-Owner)
            return Role.OPERATOR
        with self._lock:
            return self._roles.get(uid)

    def allows(self, uid: int, min_role: Role) -> bool:
        role = self.role_of(uid)
        return role is not None and role >= min_role

    def grant(self, uid: int, role: Role) -> None:
        if role is Role.OWNER or uid == self.owner_id:
            raise PermissionError("Owner role cannot be granted or modified at runtime")
        with self._lock:
            self._roles[uid] = role

    def revoke(self, uid: int) -> None:
        with self._lock:
            self._roles.pop(uid, None)

    def listing(self) -> Dict[str, str]:
        with self._lock:
            out = {str(k): v.name for k, v in self._roles.items()}
        out[str(self.owner_id)] = Role.OWNER.name
        return out


# ---------------------------------------------------------------- post-quantum & multi-vault re-exports
from .quantum_crypto import (
    HyperSovereignKeyVault,
    verify_hyper_proof,
    verify_quantum_address,
    encode_quantum_address,
    compute_hardware_puf_seal,
)
