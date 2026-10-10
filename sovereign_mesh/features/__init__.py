"""Feature catalogue assembly."""
from __future__ import annotations

from . import advanced_ops, coding, core_orchestration, discovery_design, governance
from .registry import SPEC_COUNTS, Block, Feature, FeatureInputError, FeatureRegistry, Kind

__all__ = ["build_registry", "Block", "Feature", "FeatureInputError", "FeatureRegistry", "Kind", "SPEC_COUNTS"]


def build_registry() -> FeatureRegistry:
    reg = FeatureRegistry()
    for module in (core_orchestration, discovery_design, coding, advanced_ops, governance):
        reg.extend(module.FEATURES)
    return reg
