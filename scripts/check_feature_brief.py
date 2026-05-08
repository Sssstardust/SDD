#!/usr/bin/env python3
"""
Minimal Feature Brief validation.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ambiguity_tracker import sync_ambiguity_tracker
from sdd_yaml import get_list, get_scalar, load_merged_yaml_mapping


def extract_requirement_priorities(data: dict[str, object]) -> list[str]:
    priorities: list[str] = []
    requirements = data.get("requirements")
    if not isinstance(requirements, list):
        return priorities
    for item in requirements:
        if isinstance(item, dict) and item.get("priority"):
            priorities.append(str(item["priority"]))
    return priorities


def derive_min_risk(tags: set[str]) -> str:
    if "payment" in tags:
        return "high"
    if "async" in tags and "db-change" in tags:
        return "high"
    if "security-sensitive" in tags:
        return "high"
    if "external-call" in tags and "payment" in tags:
        return "high"
    return "low"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_brief", help="Path to feature-brief.md")
    args = parser.parse_args(argv)

    path = Path(args.feature_brief)
    if not path.exists():
        print(f"[ERROR] file does not exist: {path}")
        return 1

    text = path.read_text(encoding="utf-8")
    data = load_merged_yaml_mapping(text)
    tracker = sync_ambiguity_tracker(path.parent)

    errors: list[str] = []
    warnings: list[str] = []

    if int(tracker.get("open_count", 0)) > 0:
        errors.append("open ambiguity items exist in ambiguity-tracker.json")

    required_scalar_fields = [
        "project_mode",
        "project_mode_source",
        "project_mode_confidence",
        "project_mode_confirmed_by",
        "feature_name",
        "feature_type",
        "one_liner",
        "risk_tier",
    ]
    for field in required_scalar_fields:
        if not get_scalar(data, field):
            errors.append(f"missing required field: {field}")

    project_mode = get_scalar(data, "project_mode")
    if project_mode and project_mode not in {"brownfield", "greenfield", "hybrid"}:
        errors.append(f"invalid project_mode: {project_mode}")

    tags = get_list(data, "capability_tags")
    if not tags:
        errors.append("capability_tags must not be empty")

    priorities = extract_requirement_priorities(data)
    if not priorities:
        errors.append("requirements must not be empty")
    elif "P0" not in priorities:
        errors.append("requirements must contain at least one P0 item")

    if tags:
        derived = derive_min_risk(set(tags))
        risk_tier = get_scalar(data, "risk_tier")
        if risk_tier not in {"low", "high"}:
            errors.append(f"invalid risk_tier: {risk_tier}")
        elif derived == "high" and risk_tier != "high":
            errors.append(
                f"risk_tier is too low for capability_tags; expected at least high, got {risk_tier}"
            )
        elif derived == "low" and risk_tier == "high":
            warnings.append("risk_tier is manually elevated above derived level")

    confidence = get_scalar(data, "project_mode_confidence")
    if confidence:
        try:
            value = float(confidence)
            if not (0 <= value <= 1):
                errors.append("project_mode_confidence must be between 0 and 1")
        except ValueError:
            errors.append("project_mode_confidence must be numeric")

    if errors:
        print("[FAIL] feature-brief validation failed")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("[OK] feature-brief validation passed")
    for warning in warnings:
        print(f"  [WARN] {warning}")
    print(f"  - file: {path}")
    print(
        f"  - ambiguities: {tracker.get('open_count', 0)} open / "
        f"{tracker.get('resolved_count', 0)} resolved / {tracker.get('waived_count', 0)} waived"
    )
    print(f"  - project_mode: {project_mode}")
    print(f"  - capability_tags: {', '.join(tags)}")
    print(f"  - requirements: {len(priorities)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
