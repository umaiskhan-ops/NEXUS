"""Append-only, hash-chained ledger persisted as JSON Lines."""
from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any, List, Optional, Tuple

GENESIS_HASH = "0" * 64


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _jsonable(obj: Any) -> Any:
    return json.loads(json.dumps(obj, default=str))


class HashChainLedger:
    def __init__(self, path: Optional[Path] = None):
        self._path = path
        self._blocks: List[dict] = []
        self._lock = threading.RLock()
        if path and path.exists():
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        self._blocks.append(json.loads(line))

    def append(self, task: str, payload: Any) -> dict:
        with self._lock:
            prev = self._blocks[-1]["hash"] if self._blocks else GENESIS_HASH
            data = {
                "index": len(self._blocks),
                "task": task,
                "payload": _jsonable(payload),
                "timestamp": time.time(),
                "prev_hash": prev,
            }
            block = {"hash": hashlib.sha256(_canonical(data)).hexdigest(), "data": data}
            self._blocks.append(block)
            if self._path:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(block, default=str) + "\n")
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
                if hashlib.sha256(_canonical(data)).hexdigest() != block.get("hash"):
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
