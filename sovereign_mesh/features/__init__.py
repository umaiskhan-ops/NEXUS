"""Feature catalogue assembly."""
from __future__ import annotations

from . import advanced_ops, coding, core_orchestration, discovery_design, governance
from .registry import SPEC_COUNTS, TIER_CREDIT_THRESHOLDS, Block, Feature, FeatureInputError, FeatureRegistry, FeatureTier, Kind

__all__ = ["build_registry", "Block", "Feature", "FeatureInputError", "FeatureRegistry", "FeatureTier", "Kind", "SPEC_COUNTS", "TIER_CREDIT_THRESHOLDS"]


def build_registry() -> FeatureRegistry:
    reg = FeatureRegistry()
    for module in (core_orchestration, discovery_design, coding, advanced_ops, governance):
        reg.extend(module.FEATURES)
    return reg
