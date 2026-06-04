#!/usr/bin/env python3
"""
Gate 2 report building helpers.
"""

from __future__ import annotations


def build_gate2_payload(report: dict[str, object]) -> dict[str, object]:
    summary = report.get("design_resource_claim_summary", {})
    return {
        "result": "PASS" if report.get("status") == "OK" else "FAIL",
        "checks": report.get("checks", []),
        "warnings": report.get("warnings", []),
        "errors": report.get("errors", []),
        "evidence": report.get("evidence", {}),
        "design_resource_claim_summary": summary,
        "design_resource_claim_highlights": summary.get("highlights", {}) if isinstance(summary, dict) else {},
        "truthfulness_report": report,
    }

