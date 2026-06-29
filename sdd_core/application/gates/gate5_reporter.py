#!/usr/bin/env python3
"""
Gate 5 report building helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Gate5Input:
    result: str
    test_file: str
    risk_tier: str
    coverage_result: str
    execution: dict[str, Any]
    attached_execution: dict[str, Any]
    attached_execution_required: bool
    attached_execution_requirement_reason: str
    attached_execution_admission: dict[str, Any]
    affected_component_execution_admission: dict[str, Any]
    uncovered_p0: list[str]
    uncovered_p1: list[str]
    design_resource_claim_summary: dict[str, Any]
    implementation_result: str
    implementation_report_fields: dict[str, Any]
    implementation_traceability: dict[str, Any]
    real_test_req_coverage_result: str
    real_test_req_admission: dict[str, Any]
    gate5_admission_summary: dict[str, Any]
    strict: bool
    warnings: list[str]
    errors: list[str]
    evidence: dict[str, Any]
    report_file: str


def build_gate5_section_payload(inp: Gate5Input) -> dict[str, Any]:
    return {
        "result": inp.result,
        "test_file": inp.test_file,
        "risk_tier": inp.risk_tier,
        "coverage_result": inp.coverage_result,
        "execution": inp.execution,
        "attached_execution": inp.attached_execution,
        "attached_execution_required": inp.attached_execution_required,
        "attached_execution_requirement_reason": inp.attached_execution_requirement_reason,
        "attached_execution_admission": inp.attached_execution_admission,
        "affected_component_execution_admission": inp.affected_component_execution_admission,
        "uncovered_p0": inp.uncovered_p0,
        "uncovered_p1": inp.uncovered_p1,
        "design_resource_claim_summary": inp.design_resource_claim_summary,
        "design_resource_claim_highlights": inp.design_resource_claim_summary.get("highlights", {}),
        "implementation_result": inp.implementation_result,
        **inp.implementation_report_fields,
        "implementation_traceability": inp.implementation_traceability,
        "real_test_req_coverage_result": inp.real_test_req_coverage_result,
        "real_test_req_admission": inp.real_test_req_admission,
        "gate5_admission_summary": inp.gate5_admission_summary,
        "strict": inp.strict,
        "warnings": inp.warnings,
        "errors": inp.errors,
        "evidence": inp.evidence,
        "report_file": inp.report_file,
    }
