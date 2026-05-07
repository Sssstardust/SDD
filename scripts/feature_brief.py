#!/usr/bin/env python3
"""
Helpers for reading structured metadata from feature-brief.md.
"""

from __future__ import annotations

from sdd_yaml import get_list, get_scalar, load_merged_yaml_mapping


def extract_affected_components(brief_content: str) -> list[str]:
    data = load_merged_yaml_mapping(brief_content)
    seen: set[str] = set()
    result: list[str] = []
    for item in get_list(data, "affected_components"):
        normalized = item.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def extract_risk_tier(brief_content: str) -> str:
    data = load_merged_yaml_mapping(brief_content)
    return (get_scalar(data, "risk_tier", "low") or "low").strip().lower()
