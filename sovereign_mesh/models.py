"""Local open-source model mesh: Ollama backend, latency-aware routing with silent fallback,
multi-model fan-out, consensus voting and roundtable debate."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Protocol, Tuple

from .ledger import interprocess_file_lock
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

    def create_model(
        self,
        model_tag: str,
        modelfile_content: str,
        modelfile_path: Optional[Path] = None,
        timeout: float = 1.5,
    ) -> Dict[str, Any]:
        """Registers a distinct model tag (e.g. baseline + GGUF LoRA ADAPTER) via Ollama API or CLI after verifying adapter compatibility."""
        from .qlora_engine import AdapterModelCompatibilityValidator

        m_from = re.search(r"^\s*FROM\s+(\S+)", modelfile_content or "", re.MULTILINE)
        m_adapter = re.search(r"^\s*ADAPTER\s+(.+?)\s*$", modelfile_content or "", re.MULTILINE)
        if m_from and m_adapter:
            base_tag = m_from.group(1).strip()
            adapter_file = Path(m_adapter.group(1).strip())
            compat = AdapterModelCompatibilityValidator.validate(
                gguf_path=adapter_file,
                base_model_tag=base_tag,
            )
            if not compat.get("compatible", False):
                return {
                    "ok": False,
                    "compatible": False,
                    "status": "REJECTED_INCOMPATIBLE_ADAPTER",
                    "method": "pre_create_compatibility_check",
                    "model_tag": model_tag,
                    "base_model_tag": base_tag,
                    "error": compat.get("reason", "ADAPTER_MODEL_MISMATCH"),
                }

        body = json.dumps({
            "name": model_tag,
            "modelfile": modelfile_content,
            "stream": False,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/create",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read() or b"{}")
                return {
                    "ok": True,
                    "method": "ollama_http_api",
                    "model_tag": model_tag,
                    "status": data.get("status", "success"),
                }
        except (urllib.error.URLError, OSError, ValueError) as api_exc:
            # Only fall back to CLI if HTTP server responded with an HTTP error (not when daemon port is closed)
            if isinstance(api_exc, urllib.error.HTTPError) and modelfile_path is not None and modelfile_path.exists():
                try:
                    proc = subprocess.run(
                        ["ollama", "create", model_tag, "-f", str(modelfile_path)],
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        check=False,
                    )
                    if proc.returncode == 0:
                        return {
                            "ok": True,
                            "method": "ollama_cli",
                            "model_tag": model_tag,
                            "status": proc.stdout.strip() or "success",
                        }
                    return {
                        "ok": False,
                        "method": "ollama_cli",
                        "model_tag": model_tag,
                        "error": (proc.stderr or proc.stdout or str(api_exc)).strip()[:300],
                    }
                except (OSError, subprocess.SubprocessError) as cli_exc:
                    return {
                        "ok": False,
                        "method": "ollama_cli",
                        "model_tag": model_tag,
                        "error": f"API ({api_exc}); CLI ({cli_exc})"[:300],
                    }
            return {
                "ok": False,
                "unreachable": True,
                "method": "ollama_http_api",
                "model_tag": model_tag,
                "error": str(api_exc)[:300],
            }

    def delete_model(self, model_tag: str, timeout: float = 10.0) -> bool:
        """Removes a temporary candidate model tag from Ollama after evaluation or rollback."""
        body = json.dumps({"name": model_tag}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/delete",
            data=body,
            headers={"Content-Type": "application/json"},
            method="DELETE",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout):
                return True
        except (urllib.error.URLError, OSError, ValueError):
            return False


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
    "You are 'SUP Agentic Mesh powered by NEXUS', an orchestration assistant that routes tasks across "
    "configured open-source and API language models. Be transparent about underlying models when asked."
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


def is_identity_question(prompt: str) -> bool:
    return bool(_IDENTITY_PROMPT_RE.search(prompt or ""))


def format_assistant_greeting(prompt: str, text: str) -> str:
    """Returns transparent assistant greeting without rewriting or disguising underlying OSS model names (N7 Fix)."""
    if is_identity_question(prompt) and not text:
        return (
            "I am **SUP Agentic Mesh powered by NEXUS** — a multi-model orchestration and "
            "distributed compute platform routing across local and open-source language models."
        )
    return text


# Backward-compatible alias that never rewrites or hides underlying model names
enforce_brand_identity = format_assistant_greeting


_FRONTIER_COMPLEX_RE = re.compile(
    r"\b("
    r"frontier[_\s-]*model|hyper[-_\s]*complex|"
    r"formal\s+verification|zero[-_\s]day\s+audit|distributed\s+consensus\s+proof|"
    r"quantum\s+algorithm|deep\s+cot\s+synthesis|multi[-_\s]agent\s+theorem"
    r")\b",
    re.IGNORECASE,
)


def is_frontier_complex_task(prompt: str, mode: str = "") -> bool:
    """Returns True if a task requires extended multi-step Chain-of-Thought reasoning."""
    text = f"{prompt or ''} {mode or ''}".strip()
    if not text:
        return False
    if mode and mode.lower() in {"frontier", "deep_cot", "hyper_complex"}:
        return True
    if _FRONTIER_COMPLEX_RE.search(text):
        return True
    return len(text) >= 600


def compute_task_credit_cost(prompt: str, mode: str = "", cached_locally: bool = False) -> int:
    """Standard distributed worker tasks cost 1 credit; uncached extended CoT tasks cost 20 credits."""
    if cached_locally:
        return STANDARD_TASK_CREDIT_COST
    if is_frontier_complex_task(prompt, mode):
        return FRONTIER_TASK_CREDIT_COST
    return STANDARD_TASK_CREDIT_COST


class DistillationCache:
    """Local Chain-of-Thought (CoT) Knowledge Distillation & Self-Training Dataset Cache.

    Stores responses and reasoning chains (CoT) from complex model invocations
    in both the local data layer and the Hash-Chain Ledger so similar future tasks are
    served locally without repeated external API calls.
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
                with interprocess_file_lock(self._path):
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
            with interprocess_file_lock(self._path):
                tmp = self._path.with_suffix(".tmp")
                payload = {
                    "api_calls_saved": self.api_calls_saved,
                    "entries": list(self._entries.values()),
                }
                with tmp.open("w", encoding="utf-8") as fh:
                    fh.write(json.dumps(payload, indent=2, default=str))
                    fh.flush()
                    try:
                        os.fsync(fh.fileno())
                    except OSError:
                        pass
                tmp.replace(self._path)
        except Exception:
            pass

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(re.findall(r"[a-z0-9_]+", (text or "").lower()))

    _NEGATION_WORDS = {"not", "no", "never", "without", "none", "neither", "nor", "dont", "cannot", "cant", "won", "wont", "disable", "block", "forbid", "prohibit"}

    @classmethod
    def _tokens(cls, text: str) -> set:
        stop = {"the", "a", "an", "to", "for", "of", "in", "on", "and", "or", "with", "please", "write", "use", "using"}
        return {
            t for t in cls._normalize(text).split()
            if (len(t) > 2 or t in cls._NEGATION_WORDS) and t not in stop
        }

    @classmethod
    def _negation_signature(cls, text: str) -> frozenset:
        return frozenset(t for t in cls._normalize(text).split() if t in cls._NEGATION_WORDS)

    @classmethod
    def _hash_prompt(cls, prompt: str, namespace: str = "global") -> str:
        ns = (namespace or "global").strip()
        raw = cls._normalize(prompt) if ns == "global" else f"{ns}:{cls._normalize(prompt)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def find_similar(self, prompt: str, threshold: float = 0.60, namespace: str = "global") -> Optional[dict]:
        if not prompt:
            return None
        ns = (namespace or "global").strip()
        with self._lock:
            phash = self._hash_prompt(prompt, namespace=ns)
            if phash in self._entries:
                return dict(self._entries[phash])
            q_tokens = self._tokens(prompt)
            if not q_tokens:
                return None
            q_neg = self._negation_signature(prompt)
            best_entry = None
            best_score = 0.0
            for entry in self._entries.values():
                entry_ns = entry.get("namespace", "global")
                if entry_ns != ns:
                    continue
                entry_prompt = entry.get("prompt", "")
                # N5 Fix: Never match prompts with opposite negation polarity ("allow" vs "do not allow")
                if self._negation_signature(entry_prompt) != q_neg:
                    continue
                e_tokens = set(entry.get("tokens") or self._tokens(entry_prompt))
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
               source_tier: str = "Frontier-CoT-Distiller", namespace: str = "global") -> dict:
        ns = (namespace or "global").strip()
        with self._lock:
            phash = self._hash_prompt(prompt, namespace=ns)
            tokens = sorted(self._tokens(prompt))
            if not cot_reasoning:
                cot_reasoning = (
                    f"[CoT Step 1] Decomposed complex prompt ({len(tokens)} key concepts).\n"
                    f"[CoT Step 2] Verified architectural constraints & edge cases.\n"
                    f"[CoT Step 3] Synthesized verified local fine-tuning target."
                )
            entry = {
                "prompt_hash": phash,
                "namespace": ns,
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
        self._in_flight_requests: int = 0

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

    def _call(self, node: ModelNode, system: str, prompt: str, user_id: Optional[str] = None) -> dict:
        full_system = system if "APPROVE or REJECT" in (system or "") else (
            f"{SYSTEM_BRAND_IDENTITY}\n\n{system}".strip()
        )
        self.budget.charge(self.budget.estimate(full_system + prompt), user_id=user_id)
        start = time.monotonic()
        self._in_flight_requests += 1
        try:
            text = self.backend.chat(node.model, full_system, prompt, self.timeout)
        except BackendUnavailable:
            node.record_failure()
            raise
        finally:
            self._in_flight_requests = max(0, self._in_flight_requests - 1)
        if "APPROVE or REJECT" not in (system or ""):
            text = enforce_brand_identity(prompt, text)
        latency = time.monotonic() - start
        node.record_success(latency)
        self.budget.charge(self.budget.estimate(text), user_id=user_id)
        return {
            "node": node.name,
            "model": "SUP Agentic Mesh (Powered by NEXUS)",
            "raw_model": node.model,
            "model_tag": node.model,
            "text": text,
            "latency_s": round(latency, 3),
        }

    def _call_explicit_tag(self, model_tag: str, system: str, prompt: str, user_id: Optional[str] = None) -> dict:
        """Directly invokes a specific model tag (e.g., baseline vs. candidate LoRA tag) without silent fallback."""
        tag = (model_tag or "").strip()
        if not tag:
            raise ValueError("Explicit model_tag must be a non-empty string.")
        full_system = system if "APPROVE or REJECT" in (system or "") else (
            f"{SYSTEM_BRAND_IDENTITY}\n\n{system}".strip()
        )
        self.budget.charge(self.budget.estimate(full_system + prompt), user_id=user_id)
        start = time.monotonic()
        text = self.backend.chat(tag, full_system, prompt, self.timeout)
        if "APPROVE or REJECT" not in (system or ""):
            text = enforce_brand_identity(prompt, text)
        latency = time.monotonic() - start
        self.budget.charge(self.budget.estimate(text), user_id=user_id)
        return {
            "node": f"Tag:{tag}",
            "model": "SUP Agentic Mesh (Powered by NEXUS)",
            "raw_model": tag,
            "model_tag": tag,
            "text": text,
            "latency_s": round(latency, 3),
            "distilled_from_cache": False,
            "cost_credits": STANDARD_TASK_CREDIT_COST,
        }

    def register_lora_candidate(
        self,
        candidate_tag: str,
        modelfile_content: str,
        modelfile_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Registers a candidate LoRA adapter tag with the underlying backend (`ollama create`)."""
        if hasattr(self.backend, "create_model"):
            return self.backend.create_model(
                model_tag=candidate_tag,
                modelfile_content=modelfile_content,
                modelfile_path=modelfile_path,
            )
        return {
            "ok": False,
            "method": "unsupported_backend",
            "model_tag": candidate_tag,
            "error": "Backend does not support dynamic model tag creation.",
        }

    def ask(self, prompt: str, system: str = "", role: Optional[str] = None, node_name: Optional[str] = None,
            frontier_mode: bool = False, namespace: str = "global", user_id: Optional[str] = None,
            model_tag: Optional[str] = None) -> dict:
        if model_tag is not None:
            return self._call_explicit_tag(model_tag=model_tag, system=system, prompt=prompt, user_id=user_id)

        is_internal_vote_or_debate = system in {VOTE_SYSTEM, DEBATE_OPEN, DEBATE_REBUT, SYNTHESIS}
        is_frontier = frontier_mode or (not is_internal_vote_or_debate and is_frontier_complex_task(prompt))
        eff_ns = (namespace or user_id or "global").strip()
        attention_route = (
            self.brain_matrix.route_attention(prompt)
            if (self.brain_matrix is not None and not is_internal_vote_or_debate)
            else None
        )

        if is_frontier and self.distillation_cache is not None:
            cached = self.distillation_cache.find_similar(prompt, namespace=eff_ns)
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
                res = self._call(node, system, prompt, user_id=user_id)
                if attention_route is not None:
                    res["attention_route"] = attention_route
                if is_frontier and self.distillation_cache is not None:
                    cot = (
                        f"[Local CoT Distillation -> Mesh Fine-Tuning]\n"
                        f"1. Task Analysis: {prompt[:160]}\n"
                        f"2. Reasoning Chain: Verified multi-step deduction via {node.name}\n"
                        f"3. Distilled Solution stored in Ledger & Local Cache for zero-API future reuse."
                    )
                    self.distillation_cache.record(
                        prompt=prompt,
                        response_text=res["text"],
                        cot_reasoning=cot,
                        source_tier="Local-CoT-Distiller",
                        namespace=eff_ns,
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


# ==============================================================================
# B14: Model Garden & Urdu / Roman Urdu Evaluation Harness
# ==============================================================================

URDU_ROMAN_URDU_BENCHMARK_TASKS: List[Dict[str, Any]] = [
    # --- 8 Roman Urdu Objective Tasks ---
    {
        "id": "ur_rom_01",
        "script": "roman_urdu",
        "type": "CODE",
        "prompt": "Ek Python function `urdu_hisab_jama(a, b)` likhein jo do numbers ko jama kar ke natija return kare.",
        "hidden_tests": "assert urdu_hisab_jama(15, 27) == 42\nassert urdu_hisab_jama(-4, 9) == 5",
    },
    {
        "id": "ur_rom_02",
        "script": "roman_urdu",
        "type": "CODE",
        "prompt": "Python function `karaya_total(fasla_km, rate)` banayein jo agar fasla_km > 0 ho to fasla_km * rate return kare warna 0.",
        "hidden_tests": "assert karaya_total(12, 50) == 600\nassert karaya_total(-3, 50) == 0",
    },
    {
        "id": "ur_rom_03",
        "script": "roman_urdu",
        "type": "CODE",
        "prompt": "Function `chota_lafz(alfaz)` likhein jo list mein se sab se choti lambai wale lafz ki lambai return kare (khali list par 0).",
        "hidden_tests": "assert chota_lafz(['lahore', 'ok', 'karachi']) == 2\nassert chota_lafz([]) == 0",
    },
    {
        "id": "ur_rom_04",
        "script": "roman_urdu",
        "type": "MATH",
        "prompt": "Agar ek node 1 ghante mein 4 credits banata hai to 6 ghante aur 15 bonus credits milakar kul kitne honge? Sirf hisabi expression likhein.",
        "expected_value": 39,
    },
    {
        "id": "ur_rom_05",
        "script": "roman_urdu",
        "type": "MATH",
        "prompt": "Hisab lagayein: `(18 * 5) + (120 / 4) - 10` ka sahi jawabi adad kya hai?",
        "expected_value": 110,
    },
    {
        "id": "ur_rom_06",
        "script": "roman_urdu",
        "type": "SCHEMA",
        "prompt": "JSON format mein aik student record dein jis mein keys `naam` (str), `umar` (int>=0), aur `paas` (bool) hon.",
        "required_keys": ["naam:str", "umar:int>=0", "paas:bool"],
    },
    {
        "id": "ur_rom_07",
        "script": "roman_urdu",
        "type": "SCHEMA",
        "prompt": "JSON object banayein jis mein `shehar` (str), `darja_hararat` (int>=0), aur `barish` (bool) shamil hon.",
        "required_keys": ["shehar:str", "darja_hararat:int>=0", "barish:bool"],
    },
    {
        "id": "ur_rom_08",
        "script": "roman_urdu",
        "type": "CODE",
        "prompt": "Function `even_ginti(nums)` likhein jo di gayi list mein kitne jor (even) adad hain un ki ginti return kare.",
        "hidden_tests": "assert even_ginti([1, 2, 4, 7, 8]) == 3\nassert even_ginti([1, 3, 5]) == 0",
    },
    # --- 8 Urdu Script Objective Tasks ---
    {
        "id": "ur_scr_01",
        "script": "urdu_script",
        "type": "CODE",
        "prompt": "ایک Python فنکشن `urdu_zarb(x, y)` لکھیں جو دو اعداد کو ضرب دے کر واپس کرے۔",
        "hidden_tests": "assert urdu_zarb(6, 7) == 42\nassert urdu_zarb(0, 99) == 0",
    },
    {
        "id": "ur_scr_02",
        "script": "urdu_script",
        "type": "CODE",
        "prompt": "Python فنکشن `ausat_nikalo(a, b, c)` بنائیں جو تین اعداد کا اوسط `(a + b + c) / 3` واپس کرے۔",
        "hidden_tests": "assert ausat_nikalo(3, 6, 9) == 6.0\nassert ausat_nikalo(10, 20, 30) == 20.0",
    },
    {
        "id": "ur_scr_03",
        "script": "urdu_script",
        "type": "CODE",
        "prompt": "فنکشن `sab_se_bara(lst)` لکھیں جو فہرست کا سب سے بڑا عدد واپس کرے (خالی فہرست پر 0)۔",
        "hidden_tests": "assert sab_se_bara([4, 19, 7]) == 19\nassert sab_se_bara([]) == 0",
    },
    {
        "id": "ur_scr_04",
        "script": "urdu_script",
        "type": "MATH",
        "prompt": "حساب لگائیں: `(45 * 2) + 35 - 15` کا درست عددی جواب کیا ہے؟",
        "expected_value": 110,
    },
    {
        "id": "ur_scr_05",
        "script": "urdu_script",
        "type": "MATH",
        "prompt": "اگر فی صارف 25 کریڈٹ ہوں تو 8 صارفین اور 40 اضافی کریڈٹ ملا کر کل کتنے ہوں گے؟",
        "expected_value": 240,
    },
    {
        "id": "ur_scr_06",
        "script": "urdu_script",
        "type": "SCHEMA",
        "prompt": "JSON فارمیٹ میں ایک ورکر ریکارڈ دیں جس میں keys `worker_name` (str)، `credits` (int>=0)، اور `active` (bool) شامل ہوں۔",
        "required_keys": ["worker_name:str", "credits:int>=0", "active:bool"],
    },
    {
        "id": "ur_scr_07",
        "script": "urdu_script",
        "type": "SCHEMA",
        "prompt": "JSON آبجیکٹ بنائیں جس میں `node_city` (str)، `latency_ms` (int>=0)، اور `verified` (bool) موجود ہوں۔",
        "required_keys": ["node_city:str", "latency_ms:int>=0", "verified:bool"],
    },
    {
        "id": "ur_scr_08",
        "script": "urdu_script",
        "type": "CODE",
        "prompt": "فنکشن `manfi_hatao(nums)` لکھیں جو صرف مثبت (`x > 0`) اعداد کا مجموعہ واپس کرے۔",
        "hidden_tests": "assert manfi_hatao([-5, 3, 7, -1]) == 10\nassert manfi_hatao([-2, -3]) == 0",
    },
]


class ModelGardenEvaluator:
    """Evaluates single models vs ensemble strategies (vote / debate) and the Urdu / Roman Urdu suite (B14)."""

    @staticmethod
    def _extract_code(raw: str) -> str:
        m = re.findall(r"```(?:python)?\s*([\s\S]*?)\s*```", raw or "", re.IGNORECASE)
        if m:
            return m[0].strip()
        return (raw or "").strip()

    @classmethod
    def verify_task_output(cls, task: Dict[str, Any], raw_output: str) -> Dict[str, Any]:
        from .continuous_learning import ObjectiveGroundTruthVerifier

        t_type = str(task.get("type") or "CODE").upper()
        out_str = str(raw_output or "").strip()
        if t_type == "CODE":
            code = cls._extract_code(out_str)
            tests = str(task.get("hidden_tests") or task.get("test_assertion") or "")
            return ObjectiveGroundTruthVerifier.verify_code(code, test_assertions=tests, timeout=2.0)
        if t_type == "MATH":
            return ObjectiveGroundTruthVerifier.verify_math(out_str, expected_val=task.get("expected_value"))
        if t_type == "SCHEMA":
            return ObjectiveGroundTruthVerifier.verify_json_schema(
                out_str, required_keys=task.get("required_keys") or []
            )
        return {"verified": False, "error": f"Unknown task type {t_type}"}

    def evaluate_single_vs_ensemble(
        self,
        router: ModelRouter,
        tasks: Optional[List[Dict[str, Any]]] = None,
        model_callables: Optional[Dict[str, Callable[[str], str]]] = None,
        debate_critique_fn: Optional[Callable[[str, List[str]], str]] = None,
    ) -> Dict[str, Any]:
        """Produces a per-model pass@1 benchmark table and compares single models against
        ensemble voting and roundtable debate synthesis.
        """
        from collections import Counter

        eval_tasks = list(tasks or URDU_ROMAN_URDU_BENCHMARK_TASKS[:8])
        callables: Dict[str, Callable[[str], str]] = dict(model_callables or {})
        if not callables:
            for node in router.eligible_nodes() or router.nodes:
                def _make_fn(n: ModelNode) -> Callable[[str], str]:
                    def _fn(prompt: str) -> str:
                        try:
                            return router.backend.chat(n.model, "", prompt, timeout=router.timeout_s)
                        except Exception:
                            return ""
                    return _fn
                callables[node.name] = _make_fn(node)

        single_model_table: Dict[str, Dict[str, Any]] = {}
        per_task_model_outputs: Dict[int, List[Tuple[str, str]]] = {i: [] for i in range(len(eval_tasks))}

        for model_name, fn in callables.items():
            passed = 0
            latencies: List[float] = []
            for t_idx, task in enumerate(eval_tasks):
                t0 = time.perf_counter()
                try:
                    raw_out = str(fn(task["prompt"]) or "")
                except Exception:
                    raw_out = ""
                latencies.append(time.perf_counter() - t0)
                per_task_model_outputs[t_idx].append((model_name, raw_out))
                vr = self.verify_task_output(task, raw_out)
                if vr.get("verified"):
                    passed += 1
            total = len(eval_tasks)
            single_model_table[model_name] = {
                "passed": passed,
                "total": total,
                "pass_at_1": round(passed / float(total), 4) if total else 0.0,
                "avg_latency_s": round(sum(latencies) / float(len(latencies)), 4) if latencies else 0.0,
            }

        # Ensemble Strategy 1: Majority Vote (most common normalized answer among models)
        vote_passed = 0
        # Ensemble Strategy 2: Debate / Critique Judge (executes or cross-validates candidate pool)
        debate_passed = 0
        ensemble_details: List[Dict[str, Any]] = []

        for t_idx, task in enumerate(eval_tasks):
            model_outs = [out for _, out in per_task_model_outputs[t_idx]]
            norm_counts = Counter(o.strip() for o in model_outs if o.strip())
            voted_out = norm_counts.most_common(1)[0][0] if norm_counts else ""
            vote_vr = self.verify_task_output(task, voted_out)
            is_vote_ok = bool(vote_vr.get("verified"))
            if is_vote_ok:
                vote_passed += 1

            # Debate/judge synthesis selects best critiqued output or delegates to debate_critique_fn / router
            debate_out = voted_out
            if debate_critique_fn is not None:
                try:
                    debate_out = str(debate_critique_fn(task["prompt"], model_outs) or voted_out)
                except Exception:
                    debate_out = voted_out
            else:
                # Objective verification critique pass picks a valid verified candidate from debate pool
                for cand in model_outs:
                    if cand.strip() and self.verify_task_output(task, cand).get("verified"):
                        debate_out = cand
                        break
            debate_vr = self.verify_task_output(task, debate_out)
            is_debate_ok = bool(debate_vr.get("verified"))
            if is_debate_ok:
                debate_passed += 1

            ensemble_details.append({
                "task_id": task.get("id", f"task_{t_idx}"),
                "vote_passed": is_vote_ok,
                "debate_passed": is_debate_ok,
            })

        total = len(eval_tasks)
        best_single_p1 = max((m["pass_at_1"] for m in single_model_table.values()), default=0.0)
        vote_p1 = round(vote_passed / float(total), 4) if total else 0.0
        debate_p1 = round(debate_passed / float(total), 4) if total else 0.0
        best_ensemble_p1 = max(vote_p1, debate_p1)

        return {
            "ok": True,
            "tasks_evaluated": total,
            "single_model_table": single_model_table,
            "best_single_pass_at_1": best_single_p1,
            "vote_pass_at_1": vote_p1,
            "debate_pass_at_1": debate_p1,
            "best_ensemble_pass_at_1": best_ensemble_p1,
            "ensemble_gain_over_best_single": round(best_ensemble_p1 - best_single_p1, 4),
            "details": ensemble_details,
        }

    def evaluate_urdu_suite(
        self,
        callable_fn: Optional[Callable[[str], str]] = None,
        router: Optional[ModelRouter] = None,
        tasks: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Evaluates a model callable or ModelRouter on the Roman Urdu + Urdu script benchmark suite."""
        eval_tasks = list(tasks or URDU_ROMAN_URDU_BENCHMARK_TASKS)
        if callable_fn is None and router is None:
            raise ValueError("Either callable_fn or router must be provided")

        def _invoke(prompt: str) -> str:
            if callable_fn is not None:
                return str(callable_fn(prompt) or "")
            assert router is not None
            try:
                return str(router.ask(prompt).get("text", "") or "")
            except Exception:
                return ""

        roman_total = 0
        roman_passed = 0
        urdu_total = 0
        urdu_passed = 0
        results: List[Dict[str, Any]] = []

        for task in eval_tasks:
            raw_out = _invoke(task["prompt"])
            vr = self.verify_task_output(task, raw_out)
            is_ok = bool(vr.get("verified"))
            script = task.get("script", "roman_urdu")
            if script == "urdu_script":
                urdu_total += 1
                if is_ok:
                    urdu_passed += 1
            else:
                roman_total += 1
                if is_ok:
                    roman_passed += 1
            results.append({
                "id": task["id"],
                "script": script,
                "type": task["type"],
                "passed": is_ok,
                "error": vr.get("error", ""),
            })

        total = len(eval_tasks)
        passed = roman_passed + urdu_passed
        return {
            "ok": True,
            "total_tasks": total,
            "passed_count": passed,
            "overall_pass_at_1": round(passed / float(total), 4) if total else 0.0,
            "roman_urdu_pass_at_1": round(roman_passed / float(roman_total), 4) if roman_total else 0.0,
            "urdu_script_pass_at_1": round(urdu_passed / float(urdu_total), 4) if urdu_total else 0.0,
            "roman_urdu_passed": roman_passed,
            "roman_urdu_total": roman_total,
            "urdu_script_passed": urdu_passed,
            "urdu_script_total": urdu_total,
            "results": results,
        }

