"""Feature registry: every capability is a Feature with a handler(grid, payload) -> dict.

Kinds:
  core        - implemented natively in this package
  llm         - routed to the local OSS model mesh with a task-specific system prompt
  integration - hook; needs an external adapter registered via grid.register_adapter(key, fn)
  hardware    - like integration, but always OWNER-only and behind a human approval gate
"""
from __future__ import annotations

import enum
import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..security import Role

Handler = Callable[[Any, dict], dict]


class Block(str, enum.Enum):
    CORE = "core_orchestration"
    DISCOVERY = "discovery_design"
    CODING = "coding_jit"
    ADVANCED = "advanced_ops"
    GOVERNANCE = "governance_safety"


# Counts of features mapped across the 5 logic blocks (10 + 21 + 10 + 26 + 63 = 130 features).
SPEC_COUNTS = {Block.CORE: 10, Block.DISCOVERY: 21, Block.CODING: 10, Block.ADVANCED: 26, Block.GOVERNANCE: 63}


class Kind(str, enum.Enum):
    CORE = "core"
    LLM = "llm"
    INTEGRATION = "integration"
    HARDWARE = "hardware"


class FeatureInputError(ValueError):
    pass


@dataclass(frozen=True)
class Feature:
    key: str
    name: str
    block: Block
    kind: Kind
    handler: Handler
    description: str = ""
    min_role: Role = Role.OPERATOR
    requires_approval: bool = False
    depends_on: Tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {"key": self.key, "name": self.name, "block": self.block.value, "kind": self.kind.value,
                "min_role": self.min_role.name, "requires_approval": self.requires_approval,
                "depends_on": list(self.depends_on), "description": self.description}


class FeatureRegistry:
    def __init__(self):
        self._features: Dict[str, Feature] = {}

    def register(self, feature: Feature) -> None:
        if feature.key in self._features:
            raise ValueError(f"duplicate feature key {feature.key!r}")
        self._features[feature.key] = feature

    def extend(self, features: List[Feature]) -> None:
        for f in features:
            self.register(f)

    def get(self, key: str) -> Feature:
        if key in self._features:
            return self._features[key]
        norm = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
        for f in self._features.values():
            if norm in (f.key, re.sub(r"[^a-z0-9]+", "_", f.name.lower()).strip("_")):
                return f
        raise KeyError(f"unknown feature {key!r}")

    def __contains__(self, key: str) -> bool:
        try:
            self.get(key)
            return True
        except KeyError:
            return False

    def __len__(self) -> int:
        return len(self._features)

    def all(self) -> List[Feature]:
        return list(self._features.values())

    def by_block(self, block: Block) -> List[Feature]:
        return [f for f in self._features.values() if f.block == block]

    def counts(self) -> Dict[str, int]:
        return {b.value: len(self.by_block(b)) for b in Block}

    def kind_counts(self) -> Dict[str, int]:
        return {k.value: sum(f.kind == k for f in self._features.values()) for k in Kind}

    def dependency_graph(self) -> Dict[str, List[str]]:
        return {f.key: list(f.depends_on) for f in self._features.values()}


# ---------------------------------------------------------------- helpers
def require_text(payload: dict, field: str = "text") -> str:
    text = payload.get(field)
    if not isinstance(text, str) or not text.strip():
        raise FeatureInputError(f"payload field '{field}' (non-empty string) is required")
    return text


def clamp(value: Any, lo: int, hi: int, default: int) -> int:
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return default


def extract_code(text: str) -> str:
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL)
    return (m.group(1) if m else text).strip()


def core(key: str, name: str, block: Block, handler: Handler, description: str = "", **kw) -> Feature:
    return Feature(key, name, block, Kind.CORE, handler, description, **kw)


def llm(key: str, name: str, block: Block, system_prompt: str, role: Optional[str] = None, **kw) -> Feature:
    def handler(grid, payload: dict) -> dict:
        text = payload.get("text") or json.dumps({k: v for k, v in payload.items() if k != "text"})
        if not text or text == "{}":
            raise FeatureInputError("payload 'text' is required")
        res = grid.router.ask(text, system=system_prompt, role=role)
        return {"status": "OK", "node": res["node"], "output": res["text"]}
    return Feature(key, name, block, Kind.LLM, handler, system_prompt[:160], **kw)


def integration(key: str, name: str, block: Block, requirement: str, **kw) -> Feature:
    def handler(grid, payload: dict) -> dict:
        adapter = grid.adapters.get(key)
        if adapter is None:
            return {"status": "NOT_CONFIGURED", "requirement": requirement,
                    "hint": f"grid.register_adapter('{key}', fn) where fn(grid, payload) -> dict"}
        return adapter(grid, payload)
    return Feature(key, name, block, Kind.INTEGRATION, handler, f"Requires: {requirement}", **kw)


def hardware(key: str, name: str, block: Block, requirement: str) -> Feature:
    base = integration(key, name, block, requirement)
    return Feature(key, name, block, Kind.HARDWARE, base.handler,
                   f"Physical actuation. Requires: {requirement}. OWNER-only, approval-gated.",
                   min_role=Role.OWNER, requires_approval=True, depends_on=("approval_gates", "feedback_loop_guard"))
