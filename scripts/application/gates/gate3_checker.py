#!/usr/bin/env python3
"""
Pure Gate 3 checking helpers.
"""

from __future__ import annotations


def evaluate_rule_result(*, warnings: list[str], errors: list[str]) -> str:
    if errors:
        return "FAIL"
    if warnings:
        return "WARN"
    return "PASS"


def normalize_ai_review_violations(violations: list[dict[str, object]]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for violation in violations:
        if not isinstance(violation, dict):
            continue
        normalized.append(
            {
                "severity": str(violation.get("severity") or "warn"),
                "scope": str(violation.get("scope") or "design"),
                "rationale": str(violation.get("rationale") or ""),
                "confidence": str(violation.get("confidence") or "medium"),
                "evidence_refs": [str(item) for item in violation.get("evidence_refs", []) if isinstance(item, str)],
            }
        )
    return normalized


def build_rule_modeled_ai_review(violations: list[dict[str, object]]) -> dict[str, object]:
    normalized = normalize_ai_review_violations(violations)
    return {
        "result": "WARN" if normalized else "SKIPPED",
        "mode": "rule-modeled-review" if normalized else "not-configured",
        "confidence": "medium" if normalized else None,
        "rationale": (
            "Semantic review hints were emitted from configured review rules"
            if normalized
            else "AI semantic review is not configured in the current Gate 3 implementation"
        ),
        "evidence_refs": sorted(
            {
                str(item)
                for violation in normalized
                for item in violation.get("evidence_refs", [])
                if isinstance(item, str)
            }
        ),
        "violations": normalized,
    }

