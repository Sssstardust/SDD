#!/usr/bin/env python3
"""
Shared Gate 5 admission summary helpers.
"""

from __future__ import annotations

from typing import Any


def summarize_gate5_admissions(
    *,
    real_test_req_admission: object,
    attached_execution_admission: object,
    affected_component_execution_admission: object,
) -> dict[str, Any]:
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


def summarize_gate5_admissions_from_report(report: object) -> dict[str, Any]:
    payload = report if isinstance(report, dict) else {}
    return summarize_gate5_admissions(
        real_test_req_admission=payload.get("real_test_req_admission"),
        attached_execution_admission=payload.get("attached_execution_admission"),
        affected_component_execution_admission=payload.get("affected_component_execution_admission"),
    )


def main() -> int:
    import argparse
    import json
    from sdd_core.infrastructure.versioning import detect_latest_design_path, reports_dir_for_design, resolve_feature_dir

    parser = argparse.ArgumentParser()
    parser.add_argument("feature_dir", help="specs/<feature> directory path")
    parser.add_argument("--require-attached-execution", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    args = parser.parse_args()

    feature_dir = resolve_feature_dir(args.feature_dir)
    if not feature_dir.exists():
        print(f"[FAIL] feature directory does not exist: {feature_dir}")
        return 1

    design_path = detect_latest_design_path(feature_dir)
    if not design_path.exists():
        print(f"[FAIL] missing design document: {design_path}")
        return 1

    reports_dir = reports_dir_for_design(feature_dir, design_path)
    verify_path = reports_dir / "verify-report.json"
    if not verify_path.exists():
        print(f"[FAIL] missing verify-report.json: {verify_path}")
        return 1

    try:
        report_data = json.loads(verify_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[FAIL] failed to parse verify-report.json: {exc}")
        return 1

    summary = summarize_gate5_admissions_from_report(report_data)

    if summary.get("result") == "FAIL":
        print("[FAIL] Gate 5 admissions check failed")
        print(f"  - verify report: {verify_path}")
        print(f"  - admission results: {summary.get('admission_results')}")
        print(f"  - failing admissions: {summary.get('failing_admissions')}")
        return 1

    print("[OK] Gate 5 admissions check passed")
    print(f"  - result: {summary.get('result')}")
    print(f"  - admission results: {summary.get('admission_results')}")

    # Write gate5 section to gate-report.json
    from sdd_core.infrastructure.gate_report import write_gate_section
    gate5_payload = report_data.copy()
    if "gate5_admission_summary" not in gate5_payload:
        gate5_payload["gate5_admission_summary"] = summary
    try:
        write_gate_section(
            reports_dir,
            gate_name="gate5",
            feature_name=feature_dir.name,
            design_version=design_path.name,
            payload=gate5_payload,
        )
    except Exception as exc:
        print(f"[WARN] failed to write gate5 section to gate-report.json: {exc}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

