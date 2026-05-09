#!/usr/bin/env python3
"""
Shared Gate 5 admission summary helpers.
"""

from __future__ import annotations


def summarize_gate5_admissions(
    *,
    real_test_req_admission: object,
    attached_execution_admission: object,
    affected_component_execution_admission: object,
) -> dict[str, object]:
    admissions = {
        "real_test_req": real_test_req_admission if isinstance(real_test_req_admission, dict) else {},
        "attached_execution": attached_execution_admission if isinstance(attached_execution_admission, dict) else {},
        "affected_component_execution": affected_component_execution_admission
        if isinstance(affected_component_execution_admission, dict)
        else {},
    }
    statuses = {
        name: str(admission.get("result") or "UNKNOWN")
        for name, admission in admissions.items()
    }
    failing = sorted(name for name, status in statuses.items() if status == "FAIL")
    warning = sorted(name for name, status in statuses.items() if status == "WARN")
    skipped = sorted(name for name, status in statuses.items() if status == "SKIPPED")
    passing = sorted(name for name, status in statuses.items() if status == "PASS")

    if failing:
        result = "FAIL"
    elif warning:
        result = "WARN"
    elif len(passing) == len(admissions):
        result = "PASS"
    else:
        result = "SKIPPED" if skipped else "UNKNOWN"

    return {
        "result": result,
        "admission_results": statuses,
        "failing_admissions": failing,
        "warning_admissions": warning,
        "skipped_admissions": skipped,
        "passing_admissions": passing,
        "failure_count": len(failing),
        "warning_count": len(warning),
    }


def summarize_gate5_admissions_from_report(report: object) -> dict[str, object]:
    payload = report if isinstance(report, dict) else {}
    return summarize_gate5_admissions(
        real_test_req_admission=payload.get("real_test_req_admission"),
        attached_execution_admission=payload.get("attached_execution_admission"),
        affected_component_execution_admission=payload.get("affected_component_execution_admission"),
    )
