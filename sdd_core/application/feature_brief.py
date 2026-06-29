#!/usr/bin/env python3
"""
Helpers for reading structured metadata from 需求规格.md.
"""

from __future__ import annotations

from sdd_core.domain.feature_brief import FeatureBrief


def extract_affected_components(brief_content: str) -> list[str]:
    return list(FeatureBrief.from_text(brief_content).affected_components)


def extract_risk_tier(brief_content: str) -> str:
    return FeatureBrief.from_text(brief_content).risk_tier


def parse_feature_brief(brief_content: str, *, feature_dir_name: str = "") -> FeatureBrief:
    return FeatureBrief.from_text(brief_content, feature_dir_name=feature_dir_name)

