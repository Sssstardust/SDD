#!/usr/bin/env python3
"""
Pure Gate 1 checking helpers.
"""

from __future__ import annotations


def validate_required_artifacts(*, feature_brief_exists: bool, design_exists: bool, feature_brief_path: str, design_path: str) -> list[str]:
    errors: list[str] = []
    if not feature_brief_exists:
        errors.append(f"missing feature-brief.md: {feature_brief_path}")
    if not design_exists:
        errors.append(f"missing design document: {design_path}")
    return errors


def collect_open_ambiguity_errors(tracker: object) -> list[str]:
    if not isinstance(tracker, dict):
        return []
    items = tracker.get("items")
    if not isinstance(items, list):
        return []
    errors: list[str] = []
    for item in items:
        if not isinstance(item, dict) or item.get("status") != "open":
            continue
        errors.append(f"open ambiguity {item.get('id')}: {item.get('text')}")
    return errors


def summarize_command_results(command_results: list[dict[str, object]]) -> tuple[list[str], list[str]]:
    checks: list[str] = []
    errors: list[str] = []
    for command_result in command_results:
        label = str(command_result.get("label") or "")
        if int(command_result.get("returncode") or 0) == 0:
            checks.append(label)
            continue
        output = str(command_result.get("output") or "").strip()
        errors.append(f"{label} failed: {output or 'no output'}")
    return checks, errors

