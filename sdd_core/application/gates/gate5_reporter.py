#!/usr/bin/env python3
"""
Gate 5 report building helpers.
"""

from __future__ import annotations


def build_gate5_section_payload(
    *,
    result: str,
    test_file: str,
    risk_tier: str,
    coverage_result: str,
    execution: dict[str, object],
    attached_execution: dict[str, object],
    attached_execution_required: bool,
    attached_execution_requirement_reason: str,
    attached_execution_admission: dict[str, object],
    affected_component_execution_admission: dict[str, object],
    uncovered_p0: list[str],
    uncovered_p1: list[str],
    design_resource_claim_summary: dict[str, object],
    implementation_result: str,
    implementation_report_fields: dict[str, object],
    implementation_traceability: dict[str, object],
    real_test_req_coverage_result: str,
    real_test_req_admission: dict[str, object],
    gate5_admission_summary: dict[str, object],
    strict: bool,
    warnings: list[str],
    errors: list[str],
    evidence: dict[str, object],
    report_file: str,
) -> dict[str, object]:
    return {
        "result": result,
        "test_file": test_file,
        "risk_tier": risk_tier,
        "coverage_result": coverage_result,
        "execution": execution,
        "attached_execution": attached_execution,
        "attached_execution_required": attached_execution_required,
        "attached_execution_requirement_reason": attached_execution_requirement_reason,
        "attached_execution_admission": attached_execution_admission,
        "affected_component_execution_admission": affected_component_execution_admission,
        "uncovered_p0": uncovered_p0,
        "uncovered_p1": uncovered_p1,
        "design_resource_claim_summary": design_resource_claim_summary,
        "design_resource_claim_highlights": design_resource_claim_summary.get("highlights", {}),
        "implementation_result": implementation_result,
        **implementation_report_fields,
        "implementation_traceability": implementation_traceability,
        "real_test_req_coverage_result": real_test_req_coverage_result,
        "real_test_req_admission": real_test_req_admission,
        "gate5_admission_summary": gate5_admission_summary,
        "strict": strict,
        "warnings": warnings,
        "errors": errors,
        "evidence": evidence,
        "report_file": report_file,
    }

