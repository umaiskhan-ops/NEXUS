"""Append-only, HMAC-authenticated hash-chained ledger persisted as JSON Lines."""
from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import os
import secrets
import sys
import threading
import time
from pathlib import Path
from typing import Any, Iterator, List, Optional, Tuple

GENESIS_HASH = "0" * 64


@contextlib.contextmanager
def interprocess_file_lock(target_path: Optional[Path]) -> Iterator[None]:
    """Cross-platform OS-level advisory file lock (fcntl.flock on POSIX, msvcrt.locking on Windows) for M7."""
    if not target_path:
        yield
        return
    lock_file = target_path.parent / f".{target_path.name}.lock"
    fh = None
    try:
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        fh = open(lock_file, "a+b")
        if sys.platform == "win32":
            import msvcrt
            fh.seek(0)
            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
            except OSError:
                pass
        else:
            import fcntl
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            except OSError:
                pass
        yield
    finally:
        if fh is not None:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                fh.close()
            except OSError:
                pass


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _jsonable(obj: Any) -> Any:
    return json.loads(json.dumps(obj, default=str))


class HashChainLedger:
    def __init__(self, path: Optional[Path] = None, hmac_key: Optional[str] = None):
        self._path = path
        self._blocks: List[dict] = []
        self._lock = threading.RLock()
        self._hmac_key = self._resolve_hmac_key(path, hmac_key)
        if path and path.exists():
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        self._blocks.append(json.loads(line))

    @staticmethod
    def _resolve_hmac_key(path: Optional[Path], explicit_key: Optional[str]) -> bytes:
        # M9 Fix: Derive Ledger HMAC key from environment / master passphrase secret in memory,
        # NEVER storing a plaintext '.ledger_hmac.key' file alongside ledger.jsonl in the data folder.
        raw_secret = (
            explicit_key
            or os.environ.get("LEDGER_HMAC_KEY", "").strip()
            or os.environ.get("MASTER_PASSPHRASE_HASH", "").strip()
            or os.environ.get("PEER_SHARED_SECRET", "").strip()
            or "sovereign-mesh-default-memory-hmac-key"
        )
        return hashlib.sha256(b"NEXUS_LEDGER_HMAC_V2:" + raw_secret.encode("utf-8")).digest()

    def _compute_sig(self, block_hash: str, index: int, prev_hash: str) -> str:
        msg = f"{index}:{prev_hash}:{block_hash}".encode("utf-8")
        return hmac.new(self._hmac_key, msg, hashlib.sha256).hexdigest()

    def append(self, task: str, payload: Any) -> dict:
        with self._lock:
            with interprocess_file_lock(self._path):
                prev = self._blocks[-1]["hash"] if self._blocks else GENESIS_HASH
                idx = len(self._blocks)
                data = {
                    "index": idx,
                    "task": task,
                    "payload": _jsonable(payload),
                    "timestamp": time.time(),
                    "prev_hash": prev,
                }
                block_hash = hashlib.sha256(_canonical(data)).hexdigest()
                sig = self._compute_sig(block_hash, idx, prev)
                block = {"hash": block_hash, "signature": sig, "data": data}
                self._blocks.append(block)
                if self._path:
                    self._path.parent.mkdir(parents=True, exist_ok=True)
                    with self._path.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(block, default=str) + "\n")
                        fh.flush()
                        try:
                            os.fsync(fh.fileno())
                        except OSError:
                            pass
                return block

    def verify(self) -> Tuple[bool, Optional[int]]:
        """Returns (valid, index_of_first_bad_block)."""
        with self._lock:
            prev = GENESIS_HASH
            for i, block in enumerate(self._blocks):
                if not isinstance(block, dict):
                    return False, i
                data = block.get("data")
                if not isinstance(data, dict):
                    return False, i
                if data.get("prev_hash") != prev or data.get("index") != i:
                    return False, i
                expected_hash = hashlib.sha256(_canonical(data)).hexdigest()
                if expected_hash != block.get("hash"):
                    return False, i
                block_sig = block.get("signature")
                if block_sig is not None:
                    expected_sig = self._compute_sig(expected_hash, i, prev)
                    if not hmac.compare_digest(str(block_sig), expected_sig):
                        return False, i
                prev = block["hash"]
            return True, None

    @property
    def head_hash(self) -> str:
        with self._lock:
            return self._blocks[-1]["hash"] if self._blocks else GENESIS_HASH

    def tail(self, n: int = 10) -> List[dict]:
        if n <= 0:
            return []
        with self._lock:
            return list(self._blocks[-n:])

    def range(self, start: int, end: int) -> List[dict]:
        with self._lock:
            return list(self._blocks[max(0, start):max(0, end)])

    def __len__(self) -> int:
        return len(self._blocks)
