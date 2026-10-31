"""Mutable runtime state primitives used by the feature handlers."""
from __future__ import annotations

import copy
import heapq
import itertools
import json
import math
import os
import re
import secrets
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> Counter:
    return Counter(_TOKEN_RE.findall(text.lower()))


def cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a[t] * b[t] for t in a.keys() & b.keys())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


# ---------------------------------------------------------------- memory
class MemoryStore:
    """Persistent key/value memory with lexical similarity search, session isolation & bounded retention (N9 Fix)."""

    def __init__(self, path: Optional[Path] = None, max_entries: int = 5000, ttl_seconds: float = 0.0):
        self._path = path
        self._max_entries = max(100, int(max_entries))
        self._ttl_seconds = float(ttl_seconds)
        self._lock = threading.RLock()
        self._data: Dict[str, dict] = {}
        if path and path.exists():
            self._data = json.loads(path.read_text(encoding="utf-8"))

    def _flush(self) -> None:
        if self._path:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                fh.write(json.dumps(self._data, default=str))
                fh.flush()
                try:
                    os.fsync(fh.fileno())
                except OSError:
                    pass
            tmp.replace(self._path)

    def _prune_locked(self) -> None:
        now = time.time()
        if self._ttl_seconds > 0:
            expired = [k for k, e in self._data.items() if (now - float(e.get("updated", now))) > self._ttl_seconds]
            for k in expired:
                self._data.pop(k, None)
        if len(self._data) > self._max_entries:
            by_age = sorted(self._data.items(), key=lambda kv: float(kv[1].get("updated", 0.0)))
            for k, _ in by_age[: len(self._data) - self._max_entries]:
                self._data.pop(k, None)

    def set(self, key: str, value: Any, session: str = "default") -> None:
        with self._lock:
            self._data[key] = {"value": value, "session": session, "updated": time.time()}
            self._prune_locked()
            self._flush()

    def get(self, key: str, session: Optional[str] = None) -> Any:
        with self._lock:
            self._prune_locked()
            entry = self._data.get(key)
            if not entry:
                return None
            if session is not None and entry.get("session") != session:
                return None
            return entry["value"]

    def delete(self, key: str) -> bool:
        with self._lock:
            existed = self._data.pop(key, None) is not None
            self._flush()
            return existed

    def keys(self, session: Optional[str] = None) -> List[str]:
        with self._lock:
            self._prune_locked()
            if session is not None:
                return sorted(k for k, e in self._data.items() if e.get("session") == session)
            return sorted(self._data)

    def search(self, query: str, k: int = 5, session: Optional[str] = None) -> List[Tuple[str, float, Any]]:
        q = tokenize(query)
        with self._lock:
            self._prune_locked()
            scored = [
                (key, cosine(q, tokenize(f"{key} {e['value']}")), e["value"])
                for key, e in self._data.items()
                if session is None or e.get("session") == session
            ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [s for s in scored[:k] if s[1] > 0]

    def sessions(self) -> Dict[str, int]:
        with self._lock:
            return dict(Counter(e["session"] for e in self._data.values()))

    def fuse_sessions(self, target: str = "fused") -> int:
        with self._lock:
            for e in self._data.values():
                e["session"] = target
            self._flush()
            return len(self._data)

    def export(self) -> Dict[str, dict]:
        with self._lock:
            return copy.deepcopy(self._data)

    def load(self, data: Dict[str, dict]) -> None:
        with self._lock:
            self._data = copy.deepcopy(data)
            self._flush()


# ---------------------------------------------------------------- snapshots / branches
class SnapshotManager:
    def __init__(self, limit: int = 50):
        self._snaps: Dict[str, dict] = {}
        self._order: List[str] = []
        self._limit = limit
        self._lock = threading.Lock()

    def save(self, name: str, state: dict) -> str:
        with self._lock:
            self._snaps[name] = {"state": copy.deepcopy(state), "created": time.time()}
            if name in self._order:
                self._order.remove(name)
            self._order.append(name)
            while len(self._order) > self._limit:
                self._snaps.pop(self._order.pop(0), None)
            return name

    def get(self, name: str) -> Optional[dict]:
        with self._lock:
            snap = self._snaps.get(name)
            return copy.deepcopy(snap["state"]) if snap else None

    def latest(self) -> Optional[str]:
        with self._lock:
            return self._order[-1] if self._order else None

    def names(self) -> List[str]:
        with self._lock:
            return list(self._order)


# ---------------------------------------------------------------- token budget
class BudgetExceeded(RuntimeError):
    pass


class TokenBudget:
    """Local compute guard with per-user quota tracking (N9 Fix). 'Futures' = advance reservations against the budget."""

    def __init__(self, total: int, default_user_quota: int = 0):
        self.total = total
        self.used = 0
        self.reservations: Dict[str, int] = {}
        self.default_user_quota = int(default_user_quota)
        self.user_quotas: Dict[str, int] = {}
        self.user_used: Dict[str, int] = {}
        self._lock = threading.Lock()

    @staticmethod
    def estimate(text: str) -> int:
        return max(1, len(text) // 4)

    @property
    def available(self) -> int:
        return self.total - self.used - sum(self.reservations.values())

    def set_user_quota(self, user_id: str, quota: int) -> None:
        with self._lock:
            self.user_quotas[str(user_id)] = max(0, int(quota))

    def charge(self, tokens: int, reservation: Optional[str] = None, user_id: Optional[str] = None) -> None:
        with self._lock:
            if user_id:
                uid = str(user_id)
                u_used = self.user_used.get(uid, 0)
                u_quota = self.user_quotas.get(uid, self.default_user_quota)
                if u_quota > 0 and (u_used + tokens) > u_quota:
                    raise BudgetExceeded(f"user token quota exhausted for {uid} ({u_used}/{u_quota})")
            if reservation and reservation in self.reservations:
                take = min(tokens, self.reservations[reservation])
                self.reservations[reservation] -= take
                self.used += take
                tokens -= take
            if tokens > self.available:
                raise BudgetExceeded(f"token budget exhausted ({self.used}/{self.total})")
            self.used += tokens
            if user_id:
                uid = str(user_id)
                self.user_used[uid] = self.user_used.get(uid, 0) + tokens

    def reserve(self, label: str, tokens: int) -> None:
        with self._lock:
            if tokens > self.available:
                raise BudgetExceeded(f"cannot reserve {tokens}; available {self.available}")
            self.reservations[label] = self.reservations.get(label, 0) + tokens

    def release(self, label: str) -> int:
        with self._lock:
            return self.reservations.pop(label, 0)

    def reset(self) -> None:
        with self._lock:
            self.used = 0
            self.reservations.clear()

    def status(self) -> dict:
        with self._lock:
            return {"total": self.total, "used": self.used, "reserved": dict(self.reservations),
                    "available": self.total - self.used - sum(self.reservations.values())}


# ---------------------------------------------------------------- tasks
TERMINAL = {"DONE", "FAILED", "VETOED", "REJECTED"}


@dataclass
class Task:
    id: str
    name: str
    priority: int
    payload: dict
    created_by: int
    status: str = "PENDING"
    created_at: float = field(default_factory=time.time)
    result: Any = None
    ledger_hash: str = ""
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "priority": self.priority, "status": self.status,
                "created_at": self.created_at, "ledger_hash": self.ledger_hash}


class TaskRegistry:
    """Task table + priority queue (higher priority dequeues first)."""

    def __init__(self):
        self._tasks: Dict[str, Task] = {}
        self._heap: List[Tuple[int, int, str]] = []
        self._seq = itertools.count()
        self._cond = threading.Condition()

    def create(self, name: str, payload: dict, priority: int, created_by: int) -> Task:
        task = Task(id=secrets.token_hex(4), name=name, priority=priority, payload=payload, created_by=created_by)
        with self._cond:
            self._tasks[task.id] = task
        return task

    def get(self, task_id: str) -> Optional[Task]:
        with self._cond:
            return self._tasks.get(task_id)

    def enqueue(self, task: Task) -> None:
        with self._cond:
            task.status = "QUEUED"
            heapq.heappush(self._heap, (-task.priority, next(self._seq), task.id))
            self._cond.notify()

    def next(self, timeout: float = 1.0) -> Optional[Task]:
        with self._cond:
            end = time.monotonic() + timeout
            while True:
                while self._heap:
                    _, _, tid = heapq.heappop(self._heap)
                    task = self._tasks.get(tid)
                    if task and not task.cancel_event.is_set() and task.status == "QUEUED":
                        task.status = "RUNNING"
                        return task
                remaining = end - time.monotonic()
                if remaining <= 0:
                    return None
                self._cond.wait(remaining)

    def cancel(self, target: str) -> List[str]:
        with self._cond:
            ids = list(self._tasks) if target.upper() == "ALL" else [target]
            cancelled = []
            for tid in ids:
                t = self._tasks.get(tid)
                if t and t.status not in TERMINAL:
                    t.cancel_event.set()
                    t.status = "VETOED"
                    cancelled.append(tid)
            return cancelled

    def list(self, status: Optional[str] = None) -> List[Task]:
        with self._cond:
            return [t for t in self._tasks.values() if status is None or t.status == status]

    def queue_depth(self) -> int:
        with self._cond:
            return len(self._heap)


# ---------------------------------------------------------------- scheduler
class Scheduler:
    def __init__(self):
        self._heap: List[Tuple[float, int, str]] = []
        self._jobs: Dict[str, Tuple[Callable[[], None], str]] = {}
        self._seq = itertools.count()
        self._cond = threading.Condition()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="scheduler", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._cond:
            self._cond.notify_all()

    def schedule(self, delay_s: float, callback: Callable[[], None], label: str) -> str:
        job_id = secrets.token_hex(4)
        with self._cond:
            self._jobs[job_id] = (callback, label)
            heapq.heappush(self._heap, (time.time() + max(0.0, delay_s), next(self._seq), job_id))
            self._cond.notify()
        return job_id

    def cancel(self, job_id: str) -> bool:
        with self._cond:
            return self._jobs.pop(job_id, None) is not None

    def pending(self) -> List[dict]:
        with self._cond:
            return [{"id": j, "label": self._jobs[j][1], "due": due} for due, _, j in sorted(self._heap) if j in self._jobs]

    def _loop(self) -> None:
        while not self._stop.is_set():
            with self._cond:
                if not self._heap:
                    self._cond.wait(1.0)
                    continue
                due, _, job_id = self._heap[0]
                wait = due - time.time()
                if wait > 0:
                    self._cond.wait(min(wait, 1.0))
                    continue
                heapq.heappop(self._heap)
                job = self._jobs.pop(job_id, None)
            if job:
                try:
                    job[0]()
                except Exception:  # noqa: BLE001 - scheduler must survive job failures
                    pass


# ---------------------------------------------------------------- approvals
@dataclass
class ApprovalRequest:
    id: str
    feature_key: str
    payload: dict
    requested_by: int
    reasons: List[str]
    created_at: float = field(default_factory=time.time)
    status: str = "PENDING"

    def to_dict(self) -> dict:
        return {"id": self.id, "feature": self.feature_key, "requested_by": self.requested_by,
                "reasons": self.reasons, "status": self.status, "created_at": self.created_at}


class ApprovalQueue:
    def __init__(self):
        self._reqs: Dict[str, ApprovalRequest] = {}
        self._lock = threading.Lock()

    def request(self, feature_key: str, payload: dict, requested_by: int, reasons: List[str]) -> ApprovalRequest:
        req = ApprovalRequest(secrets.token_hex(3), feature_key, payload, requested_by, reasons)
        with self._lock:
            self._reqs[req.id] = req
        return req

    def resolve(self, req_id: str, approve: bool) -> Optional[ApprovalRequest]:
        with self._lock:
            req = self._reqs.get(req_id)
            if not req or req.status != "PENDING":
                return None
            req.status = "APPROVED" if approve else "REJECTED"
            return req

    def pending(self) -> List[ApprovalRequest]:
        with self._lock:
            return [r for r in self._reqs.values() if r.status == "PENDING"]


# ---------------------------------------------------------------- triggers
class TriggerEngine:
    def __init__(self):
        self._triggers: Dict[str, dict] = {}
        self._lock = threading.Lock()

    def register(self, event: str, feature_key: str, payload: dict) -> str:
        tid = secrets.token_hex(3)
        with self._lock:
            self._triggers[tid] = {"event": event, "feature": feature_key, "payload": payload}
        return tid

    def remove(self, tid: str) -> bool:
        with self._lock:
            return self._triggers.pop(tid, None) is not None

    def matching(self, event: str) -> List[dict]:
        with self._lock:
            return [dict(t) for t in self._triggers.values() if t["event"] == event]

    def listing(self) -> Dict[str, dict]:
        with self._lock:
            return copy.deepcopy(self._triggers)
