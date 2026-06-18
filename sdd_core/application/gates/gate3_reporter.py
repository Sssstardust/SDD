#!/usr/bin/env python3
"""
Gate 3 report building helpers.
"""

from __future__ import annotations

from typing import Any


def build_gate3_payload(
    *,
    result: str,
    rule_result: str,
    checks: list[str],
    warnings: list[str],
    errors: list[str],
    ai_review: dict[str, Any],
) -> dict[str, Any]:
    return {
        "result": result,
        "rule_evaluation": {
            "result": rule_result,
            "checks": checks,
            "warnings": warnings,
            "errors": errors,
        },
        "ai_review": ai_review,
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
    }

