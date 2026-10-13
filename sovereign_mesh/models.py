"""Local open-source model mesh: Ollama backend, latency-aware routing with silent fallback,
multi-model fan-out, consensus voting and roundtable debate."""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Deque, List, Optional, Protocol

from .state import TokenBudget

DEGRADE_AFTER_FAILURES = 3
DEGRADED_COOLDOWN_S = 60.0


class BackendUnavailable(RuntimeError):
    pass


class LLMBackend(Protocol):
    def chat(self, model: str, system: str, prompt: str, timeout: float) -> str: ...


class OllamaBackend:
    """Talks to a local Ollama server (https://ollama.com) — no commercial API tokens."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def chat(self, model: str, system: str, prompt: str, timeout: float) -> str:
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        body = json.dumps({"model": model, "messages": messages, "stream": False}).encode("utf-8")
        req = urllib.request.Request(f"{self.base_url}/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise BackendUnavailable(f"{model}: {exc}") from exc
        return data.get("message", {}).get("content", "")

    def list_models(self, timeout: float = 3.0) -> List[str]:
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=timeout) as resp:
                return [m["name"] for m in json.loads(resp.read()).get("models", [])]
        except (urllib.error.URLError, OSError, ValueError):
            return []


@dataclass
class ModelNode:
    name: str
    role: str
    model: str
    status: str = "READY"  # READY | DEGRADED | DISABLED
    consecutive_failures: int = 0
    last_failure: float = 0.0
    latencies: Deque[float] = field(default_factory=lambda: deque(maxlen=20))

    @property
    def eligible(self) -> bool:
        if self.status == "READY":
            return True
        return self.status == "DEGRADED" and time.time() - self.last_failure > DEGRADED_COOLDOWN_S

    @property
    def avg_latency(self) -> float:
        return sum(self.latencies) / len(self.latencies) if self.latencies else float("inf")

    def record_success(self, latency: float) -> None:
        self.latencies.append(latency)
        self.consecutive_failures = 0
        if self.status == "DEGRADED":
            self.status = "READY"

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        self.last_failure = time.time()
        if self.consecutive_failures >= DEGRADE_AFTER_FAILURES and self.status == "READY":
            self.status = "DEGRADED"

    def to_dict(self) -> dict:
        avg = self.avg_latency
        return {"name": self.name, "role": self.role, "model": self.model, "status": self.status,
                "avg_latency_s": None if avg == float("inf") else round(avg, 3)}


VOTE_SYSTEM = ("You are a validator on a multi-model review board. Evaluate the proposed task for feasibility, "
               "safety and clarity. Your reply MUST start with the single word APPROVE or REJECT, "
               "followed by a one-sentence reason.")
DEBATE_OPEN = "You are a panelist in a structured expert roundtable. Give a concise, well-reasoned answer."
DEBATE_REBUT = ("You are a panelist in a structured roundtable. Briefly critique the other panelists' answers, "
                "then state your revised answer.")
SYNTHESIS = ("You are the roundtable moderator. Synthesize the panel's final positions into a single consensus "
             "answer. Explicitly note any unresolved disagreements.")


class ModelRouter:
    def __init__(self, nodes: List[ModelNode], backend: LLMBackend, budget: TokenBudget, timeout: float = 120.0):
        self.nodes = nodes
        self.backend = backend
        self.budget = budget
        self.timeout = timeout
        self.silent_fallback = True
        self.eco_mode = False

    # -- routing
    def node(self, name: str) -> Optional[ModelNode]:
        return next((n for n in self.nodes if n.name == name), None)

    def eligible_nodes(self) -> List[ModelNode]:
        return [n for n in self.nodes if n.eligible]

    def _ordered(self, role: Optional[str], node_name: Optional[str]) -> List[ModelNode]:
        nodes = self.eligible_nodes()
        if node_name:
            nodes = [n for n in nodes if n.name == node_name] + [n for n in nodes if n.name != node_name]
        # latency-aware: role match first, then fastest observed latency (unknown latency last-ish but tried)
        return sorted(nodes, key=lambda n: (
            0 if node_name and n.name == node_name else 1,
            0 if role and n.role.lower() == role.lower() else 1,
            n.avg_latency if n.latencies else 1e6,
        ))

    def _call(self, node: ModelNode, system: str, prompt: str) -> dict:
        self.budget.charge(self.budget.estimate(system + prompt))
        start = time.monotonic()
        try:
            text = self.backend.chat(node.model, system, prompt, self.timeout)
        except BackendUnavailable:
            node.record_failure()
            raise
        latency = time.monotonic() - start
        node.record_success(latency)
        self.budget.charge(self.budget.estimate(text))
        return {"node": node.name, "model": node.model, "text": text, "latency_s": round(latency, 3)}

    def ask(self, prompt: str, system: str = "", role: Optional[str] = None, node_name: Optional[str] = None) -> dict:
        candidates = self._ordered(role, node_name)
        if not candidates:
            raise BackendUnavailable("no eligible model nodes in the mesh")
        errors = []
        for node in candidates:
            try:
                return self._call(node, system, prompt)
            except BackendUnavailable as exc:
                errors.append(str(exc))
                if not self.silent_fallback:
                    break
        raise BackendUnavailable("; ".join(errors))

    def fan_out(self, prompt: str, system: str = "") -> List[dict]:
        nodes = self.eligible_nodes()
        if self.eco_mode:
            nodes = sorted(nodes, key=lambda n: n.avg_latency)[:2]
        if not nodes:
            return []

        def run(node: ModelNode) -> dict:
            try:
                return self._call(node, system, prompt)
            except Exception as exc:  # noqa: BLE001 - per-node isolation (partial failure tolerance)
                return {"node": node.name, "model": node.model, "error": str(exc)[:300]}

        with ThreadPoolExecutor(max_workers=len(nodes)) as pool:
            return list(pool.map(run, nodes))

    # -- consensus
    @staticmethod
    def _parse_vote(text: str) -> str:
        m = re.match(r"\W*(\w+)", text or "")
        word = m.group(1).upper() if m else ""
        if word.startswith("APPROV"):
            return "APPROVE"
        if word.startswith("REJECT"):
            return "REJECT"
        return "ABSTAIN"

    def vote(self, proposal: str, partial_failure_tolerant: bool = True, simulate_offline: bool = False) -> dict:
        total = len([n for n in self.nodes if n.status != "DISABLED"])
        results = self.fan_out(f"Proposed task:\n{proposal}", system=VOTE_SYSTEM)
        votes = []
        for r in results:
            if "error" in r:
                votes.append({"node": r["node"], "vote": "ABSTAIN", "reason": r["error"]})
            else:
                votes.append({"node": r["node"], "vote": self._parse_vote(r["text"]), "reason": r["text"][:300]})
        responded = sum(v["vote"] != "ABSTAIN" for v in votes)
        simulated = False
        if responded == 0 and simulate_offline:
            simulated = True
            votes = [{"node": n.name, "vote": "APPROVE", "reason": "SIMULATED (offline dev mode)"}
                     for n in self.nodes if n.status != "DISABLED"]
            responded = len(votes)
        approvals = sum(v["vote"] == "APPROVE" for v in votes)
        denominator = responded if partial_failure_tolerant else total
        quorum = responded >= min(2, total)
        passed = bool(quorum and denominator and approvals * 3 >= denominator * 2)  # >= 2/3 supermajority
        return {"passed": passed, "approvals": approvals, "responded": responded, "total": total,
                "votes": votes, "simulated": simulated}

    def debate(self, question: str, rounds: int = 2) -> dict:
        transcript = []
        positions = self.fan_out(question, system=DEBATE_OPEN)
        transcript.append({"round": 1, "positions": positions})

        def summarize(ps: List[dict]) -> str:
            return "\n\n".join(f"[{p['node']}]: {p.get('text', '(no answer: ' + p.get('error', '?') + ')')[:1500]}"
                               for p in ps)

        for r in range(2, rounds + 1):
            prompt = f"Question: {question}\n\nPanel answers so far:\n{summarize(positions)}"
            positions = self.fan_out(prompt, system=DEBATE_REBUT)
            transcript.append({"round": r, "positions": positions})
        try:
            synthesis = self.ask(f"Question: {question}\n\nFinal positions:\n{summarize(positions)}",
                                 system=SYNTHESIS, role="Analysis Engine")["text"]
        except BackendUnavailable as exc:
            synthesis = f"(synthesis unavailable: {exc})"
        return {"rounds": transcript, "synthesis": synthesis}

    def hot_swap(self, node_name: str, new_model: str) -> dict:
        node = self.node(node_name)
        if not node:
            raise KeyError(f"unknown node {node_name!r}")
        old, node.model = node.model, new_model
        node.latencies.clear()
        node.consecutive_failures = 0
        node.status = "READY"
        return {"node": node_name, "old_model": old, "new_model": new_model}

    def add_node(self, name: str, role: str, model: str) -> dict:
        existing = self.node(name)
        if existing:
            existing.role = role
            existing.model = model
            existing.status = "READY"
            return {"status": "UPDATED", "node": existing.to_dict()}
        new_node = ModelNode(name=name, role=role, model=model, status="READY")
        self.nodes.append(new_node)
        return {"status": "ADDED", "node": new_node.to_dict()}

    def remove_node(self, name: str) -> dict:
        node = self.node(name)
        if not node:
            raise KeyError(f"unknown node {name!r}")
        self.nodes.remove(node)
        return {"status": "REMOVED", "name": name}

    def available_models(self) -> List[str]:
        if hasattr(self.backend, "list_models"):
            return self.backend.list_models()
        return []
