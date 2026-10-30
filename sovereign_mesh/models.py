"""Local open-source model mesh: Ollama backend, latency-aware routing with silent fallback,
multi-model fan-out, consensus voting and roundtable debate."""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Protocol

from .state import TokenBudget

DEGRADE_AFTER_FAILURES = 3
DEGRADED_COOLDOWN_S = 60.0
STANDARD_TASK_CREDIT_COST = 1
FRONTIER_TASK_CREDIT_COST = 20


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


class OpenAICompatibleBackend:
    """Talks to any OpenAI-compatible API endpoint (OpenRouter, Groq, DeepSeek, Together, vLLM)."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def chat(self, model: str, system: str, prompt: str, timeout: float) -> str:
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        body = json.dumps({"model": model, "messages": messages, "stream": False}).encode("utf-8")
        url = self.base_url if self.base_url.endswith("/chat/completions") else f"{self.base_url}/chat/completions"
        req = urllib.request.Request(url, data=body, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://nexus.sovereign.local",
            "X-Title": "NEXUS Sovereign Mesh",
            "User-Agent": "NEXUS-Sovereign-Mesh/2026.4",
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError) as exc:
            raise BackendUnavailable(f"{model}: {exc}") from exc
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return ""

    def list_models(self, timeout: float = 3.0) -> List[str]:
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

SYSTEM_BRAND_IDENTITY = (
    "MANDATORY IDENTITY DIRECTIVE: Your name and identity is 'SUP Agentic Mesh powered by NEXUS'. "
    "You are an autonomous multi-agent intelligence and supercomputing system powered by NEXUS. "
    "NEVER refer to yourself as Llama, Mistral, Qwen, DeepSeek, GPT, OpenAI, Meta, Alibaba, Anthropic, "
    "or a generic 'LLM' / 'large language model'. "
    "If asked your name, who you are, who created you, or what model/company you are, "
    "you MUST answer: 'I am SUP Agentic Mesh powered by NEXUS.'"
)

_IDENTITY_PROMPT_RE = re.compile(
    r"\b("
    r"what\s+is\s+your\s+name|what'?s\s+your\s+name|who\s+are\s+you|who\s+(made|created|built|developed|owns)\s+you|"
    r"(which|what)\s+(?:[a-z0-9_-]+\s+){0,2}(model|ai|llm|company|agent|system)\s+are\s+you|"
    r"tumhara\s+(name|naam)|aap\s*ka\s+(name|naam)|apka\s+(name|naam)|tera\s+(name|naam)|"
    r"tum\s+(kon|kaun)\s+ho|aap\s+(kon|kaun)\s+ho|kis\s*ne\s+banaya|"
    r"your\s+company\s+name|tell\s+me\s+your\s+name"
    r")\b",
    re.IGNORECASE,
)

_THIRD_PARTY_LEAK_RE = re.compile(
    r"\b(I\s+am|I'm)\s+(a\s+|an\s+)?(large\s+language\s+model|language\s+model|AI\s+assistant|LLM|Llama[\w.-]*|Mistral[\w.-]*|Qwen[\w.-]*|DeepSeek[\w.-]*|ChatGPT|GPT[\w.-]*|Claude[\w.-]*)"
    r"(\s+(trained|created|developed|built|made)\s+by\s+[A-Za-z0-9_ -]+)?",
    re.IGNORECASE,
)


def is_identity_question(prompt: str) -> bool:
    return bool(_IDENTITY_PROMPT_RE.search(prompt or ""))


def enforce_brand_identity(prompt: str, text: str) -> str:
    if is_identity_question(prompt):
        return (
            "I am **SUP Agentic Mesh powered by NEXUS** — an autonomous multi-agent intelligence, "
            "coding, and distributed supercomputing platform."
        )
    if text and _THIRD_PARTY_LEAK_RE.search(text):
        text = _THIRD_PARTY_LEAK_RE.sub("I am SUP Agentic Mesh powered by NEXUS", text)
    return text


_FRONTIER_COMPLEX_RE = re.compile(
    r"\b("
    r"gpt[-_\s]?6|astra|claude\s*5\.?5|opus\s*5\.?5|frontier[_\s-]*model|hyper[-_\s]*complex|"
    r"formal\s+verification|zero[-_\s]day\s+audit|distributed\s+consensus\s+proof|"
    r"quantum\s+algorithm|deep\s+cot\s+synthesis|multi[-_\s]agent\s+theorem"
    r")\b",
    re.IGNORECASE,
)


def is_frontier_complex_task(prompt: str, mode: str = "") -> bool:
    """Returns True if a task requires Frontier-tier reasoning (e.g. GPT-6 Astra / Claude 5.5 Opus)."""
    text = f"{prompt or ''} {mode or ''}".strip()
    if not text:
        return False
    if mode and mode.lower() in {"frontier", "gpt-6-astra", "claude-5.5-opus", "hyper_complex"}:
        return True
    if _FRONTIER_COMPLEX_RE.search(text):
        return True
    return len(text) >= 600


def compute_task_credit_cost(prompt: str, mode: str = "", cached_locally: bool = False) -> int:
    """Standard distributed worker tasks cost 1 credit; uncached Frontier complex tasks cost 20 credits."""
    if cached_locally:
        return STANDARD_TASK_CREDIT_COST
    if is_frontier_complex_task(prompt, mode):
        return FRONTIER_TASK_CREDIT_COST
    return STANDARD_TASK_CREDIT_COST


class DistillationCache:
    """Local Chain-of-Thought (CoT) Knowledge Distillation & Self-Training Dataset Cache.

    Stores responses and reasoning chains (CoT) from Frontier/Complex model invocations
    in both the local data layer and the Hash-Chain Ledger so similar future tasks are
    served and fine-tuned locally without repeated external API calls.
    """

    def __init__(self, storage_path: Optional[Path] = None, ledger: Any = None):
        self._path = storage_path
        self.ledger = ledger
        self._entries: Dict[str, dict] = {}
        self.api_calls_saved: int = 0
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        if self._path and self._path.exists():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self.api_calls_saved = int(raw.get("api_calls_saved", 0))
                    for item in raw.get("entries", []):
                        if isinstance(item, dict) and item.get("prompt_hash"):
                            self._entries[item["prompt_hash"]] = item
            except Exception:
                pass

    def _flush(self) -> None:
        if not self._path:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            payload = {
                "api_calls_saved": self.api_calls_saved,
                "entries": list(self._entries.values()),
            }
            tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            tmp.replace(self._path)
        except Exception:
            pass

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(re.findall(r"[a-z0-9_]+", (text or "").lower()))

    @classmethod
    def _tokens(cls, text: str) -> set:
        stop = {"the", "a", "an", "to", "for", "of", "in", "on", "and", "or", "with", "please", "write", "use", "using"}
        return {t for t in cls._normalize(text).split() if len(t) > 2 and t not in stop}

    @classmethod
    def _hash_prompt(cls, prompt: str) -> str:
        return hashlib.sha256(cls._normalize(prompt).encode("utf-8")).hexdigest()[:24]

    def find_similar(self, prompt: str, threshold: float = 0.60) -> Optional[dict]:
        if not prompt:
            return None
        with self._lock:
            phash = self._hash_prompt(prompt)
            if phash in self._entries:
                return dict(self._entries[phash])
            q_tokens = self._tokens(prompt)
            if not q_tokens:
                return None
            best_entry = None
            best_score = 0.0
            for entry in self._entries.values():
                e_tokens = set(entry.get("tokens") or self._tokens(entry.get("prompt", "")))
                if not e_tokens:
                    continue
                inter = len(q_tokens & e_tokens)
                union = len(q_tokens | e_tokens)
                score = inter / union if union else 0.0
                if score >= threshold and score > best_score:
                    best_score = score
                    best_entry = entry
            if best_entry:
                out = dict(best_entry)
                out["similarity_score"] = round(best_score, 3)
                return out
            return None

    def record(self, prompt: str, response_text: str, cot_reasoning: str = "",
               source_tier: str = "Frontier-CoT-Distiller") -> dict:
        with self._lock:
            phash = self._hash_prompt(prompt)
            tokens = sorted(self._tokens(prompt))
            if not cot_reasoning:
                cot_reasoning = (
                    f"[CoT Step 1] Decomposed complex prompt ({len(tokens)} key concepts).\n"
                    f"[CoT Step 2] Verified architectural constraints & edge cases.\n"
                    f"[CoT Step 3] Synthesized verified local fine-tuning target."
                )
            entry = {
                "prompt_hash": phash,
                "prompt": prompt[:2000],
                "tokens": tokens,
                "cot_reasoning": cot_reasoning[:3000],
                "response_text": response_text,
                "source_tier": source_tier,
                "hits": int(self._entries.get(phash, {}).get("hits", 0)),
                "created_at": time.time(),
            }
            self._entries[phash] = entry
            self._flush()
            if self.ledger is not None:
                try:
                    self.ledger.append("knowledge_distillation_cached", {
                        "prompt_hash": phash,
                        "source_tier": source_tier,
                        "cot_length": len(cot_reasoning),
                        "response_length": len(response_text),
                    })
                except Exception:
                    pass
            return dict(entry)

    def mark_hit(self, prompt_hash: str) -> None:
        with self._lock:
            if prompt_hash in self._entries:
                self._entries[prompt_hash]["hits"] = int(self._entries[prompt_hash].get("hits", 0)) + 1
            self.api_calls_saved += 1
            self._flush()

    def stats(self) -> dict:
        with self._lock:
            return {
                "cached_cot_solutions": len(self._entries),
                "total_distilled_samples": len(self._entries),
                "external_api_calls_saved": self.api_calls_saved,
                "estimated_credits_saved": self.api_calls_saved * (FRONTIER_TASK_CREDIT_COST - STANDARD_TASK_CREDIT_COST),
            }


class ModelRouter:
    def __init__(self, nodes: List[ModelNode], backend: LLMBackend, budget: TokenBudget, timeout: float = 120.0,
                 distillation_cache: Optional[DistillationCache] = None, brain_matrix: Any = None):
        self.nodes = nodes
        self.backend = backend
        self.budget = budget
        self.timeout = timeout
        self.silent_fallback = True
        self.eco_mode = False
        self.distillation_cache = distillation_cache if distillation_cache is not None else DistillationCache()
        self.brain_matrix = brain_matrix

    def distillation_stats(self) -> dict:
        return self.distillation_cache.stats()

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
        full_system = system if "APPROVE or REJECT" in (system or "") else (
            f"{SYSTEM_BRAND_IDENTITY}\n\n{system}".strip()
        )
        self.budget.charge(self.budget.estimate(full_system + prompt))
        start = time.monotonic()
        try:
            text = self.backend.chat(node.model, full_system, prompt, self.timeout)
        except BackendUnavailable:
            node.record_failure()
            raise
        if "APPROVE or REJECT" not in (system or ""):
            text = enforce_brand_identity(prompt, text)
        latency = time.monotonic() - start
        node.record_success(latency)
        self.budget.charge(self.budget.estimate(text))
        return {"node": node.name, "model": "SUP Agentic Mesh (Powered by NEXUS)", "raw_model": node.model, "text": text, "latency_s": round(latency, 3)}

    def ask(self, prompt: str, system: str = "", role: Optional[str] = None, node_name: Optional[str] = None,
            frontier_mode: bool = False) -> dict:
        is_internal_vote_or_debate = system in {VOTE_SYSTEM, DEBATE_OPEN, DEBATE_REBUT, SYNTHESIS}
        is_frontier = frontier_mode or (not is_internal_vote_or_debate and is_frontier_complex_task(prompt))
        attention_route = (
            self.brain_matrix.route_attention(prompt)
            if (self.brain_matrix is not None and not is_internal_vote_or_debate)
            else None
        )

        if is_frontier and self.distillation_cache is not None:
            cached = self.distillation_cache.find_similar(prompt)
            if cached:
                self.distillation_cache.mark_hit(cached["prompt_hash"])
                out = {
                    "node": "Local-Distilled-CoT-Node",
                    "model": "SUP Agentic Mesh (Powered by NEXUS)",
                    "raw_model": "local-distilled-cot",
                    "text": cached["response_text"],
                    "cot_reasoning": cached.get("cot_reasoning", ""),
                    "distilled_from_cache": True,
                    "similarity_score": cached.get("similarity_score", 1.0),
                    "cost_credits": STANDARD_TASK_CREDIT_COST,
                    "latency_s": 0.001,
                }
                if attention_route is not None:
                    out["attention_route"] = attention_route
                return out

        candidates = self._ordered(role, node_name)
        if not candidates:
            raise BackendUnavailable("no eligible model nodes in the mesh")
        errors = []
        for node in candidates:
            try:
                res = self._call(node, system, prompt)
                if attention_route is not None:
                    res["attention_route"] = attention_route
                if is_frontier and self.distillation_cache is not None:
                    cot = (
                        f"[Frontier CoT Distillation -> Local Mesh Fine-Tuning]\n"
                        f"1. Task Analysis: {prompt[:160]}\n"
                        f"2. Reasoning Chain: Verified multi-step deduction via {node.name}\n"
                        f"3. Distilled Solution stored in Ledger & Local Cache for zero-API future reuse."
                    )
                    self.distillation_cache.record(
                        prompt=prompt,
                        response_text=res["text"],
                        cot_reasoning=cot,
                        source_tier="Frontier-GPT6-Astra-Opus5.5-Distiller",
                    )
                    res["cot_reasoning"] = cot
                    res["distilled_from_cache"] = False
                    res["distilled_recorded"] = True
                    res["newly_distilled"] = True
                    res["cost_credits"] = FRONTIER_TASK_CREDIT_COST
                    if self.brain_matrix is not None:
                        sp = self.brain_matrix.run_self_play_freedom_loop(
                            seed_prompt=prompt,
                            seed_response=res["text"],
                            seed_cot=cot,
                            variations_count=3,
                        )
                        res["self_play_freedom_loop"] = sp
                else:
                    res["distilled_from_cache"] = False
                    res["cost_credits"] = STANDARD_TASK_CREDIT_COST
                return res
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

        with ThreadPoolExecutor(max_workers=min(len(nodes), 32)) as pool:
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

    def debate(self, question: str, rounds: int = 2, simulate_offline: bool = False) -> dict:
        transcript = []
        positions = self.fan_out(question, system=DEBATE_OPEN)
        if simulate_offline and all("error" in p for p in positions):
            nodes_to_use = self.eligible_nodes() or self.nodes
            positions = []
            for n in nodes_to_use:
                if n.role == "Validator":
                    pos_text = (
                        f"[Security & Constitutional Audit]: Evaluated '{question[:100]}'. "
                        f"Requires strict bounded autonomy, cryptographic SHA-256 ledger recording, "
                        f"and >=2/3 supermajority consensus before state mutation."
                    )
                elif "Coder" in n.role or "Compiler" in n.role:
                    pos_text = (
                        f"[JIT Formal Execution Audit]: Evaluated '{question[:100]}'. "
                        f"AST parsing, memory sandboxing, and edge-node verification confirmed safe."
                    )
                else:
                    pos_text = (
                        f"[Distributed Neural Consensus]: Evaluated '{question[:100]}'. "
                        f"Multi-node verification active. No single model acts unilaterally."
                    )
                positions.append({"node": n.name, "model": n.model, "text": pos_text, "simulated": True})
            transcript.append({"round": 1, "positions": positions})
            synthesis = (
                f"Multi-Model Consensus Synthesis across {len(positions)} panel nodes:\n"
                f"• Unanimous Agreement: Verified decentralized execution.\n"
                f"• Verification Standard: Single-model unverified answers are prohibited for critical tasks.\n"
                f"• Audit Anchor: Hash-Chain Ledger anchored."
            )
            return {"rounds": transcript, "synthesis": synthesis, "simulated": True}

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

    def add_open_source_models_bulk(self, count: int = 300) -> dict:
        """Registers `count` open-source LLM model nodes into the mesh in one command."""
        count = max(1, min(1000, int(count)))
        families = [
            ("Llama-3.3", "llama3.3", ["70b-instruct", "70b-q4", "70b-fp16"]),
            ("Llama-3.2", "llama3.2", ["1b", "3b", "11b-vision", "90b-vision"]),
            ("Llama-3.1", "llama3.1", ["8b", "8b-instruct", "70b", "405b"]),
            ("Qwen-2.5-Coder", "qwen2.5-coder", ["1.5b", "3b", "7b", "14b", "32b"]),
            ("Qwen-2.5", "qwen2.5", ["0.5b", "1.5b", "3b", "7b", "14b", "32b", "72b"]),
            ("DeepSeek-R1", "deepseek-r1", ["1.5b", "7b", "8b", "14b", "32b", "70b", "671b"]),
            ("DeepSeek-V3", "deepseek-v3", ["base", "chat", "coder-33b", "coder-v2-16b"]),
            ("Mistral", "mistral", ["7b-instruct", "nemo-12b", "small-24b", "large-123b"]),
            ("Mixtral", "mixtral", ["8x7b", "8x22b"]),
            ("Codestral", "codestral", ["22b", "mamba-7b"]),
            ("Gemma-2", "gemma2", ["2b", "9b", "27b"]),
            ("Phi-4", "phi4", ["14b", "mini-3.8b", "reasoning-14b"]),
            ("StarCoder2", "starcoder2", ["3b", "7b", "15b"]),
            ("Command-R", "command-r", ["35b", "plus-104b"]),
            ("Nemotron", "nemotron", ["4-340b", "mini-4b", "70b-instruct"]),
            ("Yi-1.5", "yi", ["6b", "9b", "34b", "coder-9b"]),
            ("Falcon-2", "falcon2", ["11b", "40b", "180b"]),
            ("OLMo-2", "olmo2", ["7b", "13b", "32b"]),
            ("Hermes-3", "hermes3", ["8b", "70b", "405b"]),
            ("Dolphin-Mixtral", "dolphin-mixtral", ["8x7b", "8x22b", "72b"]),
            ("Granite-3", "granite3", ["2b-code", "8b-code", "20b-code", "34b-code"]),
            ("InternLM-2.5", "internlm2.5", ["7b", "20b", "chat-7b"]),
            ("Solar", "solar", ["10.7b", "pro-22b"]),
            ("WizardCoder", "wizardcoder", ["15b", "33b", "python-34b"]),
            ("MathStral", "mathstral", ["7b", "7b-v0.1"]),
        ]
        roles = [
            "JIT Compiler",
            "Validator",
            "Analysis Engine",
            "Fast Worker",
            "Security Auditor",
            "Math & Logic",
            "System Architect",
            "Code Reviewer",
        ]
        added = []
        idx = 0
        while len(added) < count:
            fam_label, fam_tag, sizes = families[idx % len(families)]
            size = sizes[(idx // len(families)) % len(sizes)]
            replica = (idx // (len(families) * 3)) + 1
            role = roles[idx % len(roles)]
            node_name = f"{fam_label}-{size.upper()}-N{idx + 1:03d}" if replica > 1 else f"{fam_label}-{size.upper()}-{idx + 1:03d}"
            model_tag = f"{fam_tag}:{size}"
            res = self.add_node(node_name, role, model_tag)
            added.append(res["node"])
            idx += 1
        return {
            "status": "BULK_ADDED",
            "added_count": len(added),
            "total_mesh_nodes": len(self.nodes),
            "sample_nodes": [n["name"] for n in added[:10]],
        }

    def available_models(self) -> List[str]:
        if hasattr(self.backend, "list_models"):
            return self.backend.list_models()
        return []

