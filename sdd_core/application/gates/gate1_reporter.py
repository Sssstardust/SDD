#!/usr/bin/env python3
"""
Gate 1 report building helpers.
"""

from __future__ import annotations


def build_gate1_payload(
    *,
    checks: list[str],
    warnings: list[str],
    errors: list[str],
    commands: list[dict[str, object]],
    ambiguity_tracker: str | None,
    design_pack_snapshot: str | None,
    evidence: dict[str, object],
) -> dict[str, object]:
    return {
        "result": "PASS" if not errors else "FAIL",
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
        "commands": commands,
        "ambiguity_tracker": ambiguity_tracker,
        "design_pack_snapshot": design_pack_snapshot,
        "evidence": evidence,
    }

