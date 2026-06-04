#!/usr/bin/env python3
"""
Shared state formatting helpers for flow-status / overview / console / next.
"""

from __future__ import annotations


def strict_flag(state: dict[str, object]) -> str:
    return "strict" if state.get("strict_next_step") else ("recommended" if state.get("strict_recommended") else "no")


def framework_badges(state: dict[str, object]) -> str:
    evidence = state.get("implementation_framework_evidence")
    if not isinstance(evidence, dict) or not evidence:
        return "N/A"
    parts: list[str] = []
    inherited = evidence.get("inherited_matches")
    if isinstance(inherited, int) and inherited > 0:
        parts.append(f"inherit={inherited}")
    mybatis = evidence.get("mybatis_bound_matches")
    if isinstance(mybatis, int) and mybatis > 0:
        parts.append(f"mybatis={mybatis}")
    result_maps = evidence.get("mybatis_result_map_matches")
    if isinstance(result_maps, int) and result_maps > 0:
        parts.append(f"resultMap={result_maps}")
    missing_method_details = state.get("implementation_missing_method_details")
    if isinstance(missing_method_details, list) and missing_method_details:
        parts.append(f"missingMethod={len(missing_method_details)}")
    return ", ".join(parts) if parts else "N/A"


def real_test_admission_badge(state: dict[str, object]) -> str:
    admission = state.get("real_test_req_admission")
    if not isinstance(admission, dict) or not admission:
        return "N/A"
    result = str(admission.get("result") or "N/A")
    requirement = str(admission.get("requirement") or "").strip()
    missing = admission.get("missing_required_req_ids")
    parts = [result]
    if requirement:
        parts.append(requirement)
    if isinstance(missing, list) and missing:
        parts.append(f"missing={len(missing)}")
    return " ".join(parts)


def attached_execution_admission_badge(state: dict[str, object]) -> str:
    admission = state.get("attached_execution_admission")
    if not isinstance(admission, dict) or not admission:
        return "N/A"
    result = str(admission.get("result") or "N/A")
    reason = str(admission.get("requirement_reason") or "").strip()
    required = admission.get("required")
    failed_components = admission.get("failed_components")
    failed_commands = admission.get("failed_commands")
    parts = [result]
    if required is True:
        parts.append("required")
    elif required is False and reason != "optional":
        parts.append("optional")
    if reason:
        parts.append(reason)
    if isinstance(failed_components, list) and failed_components:
        parts.append("failed@" + ",".join(str(item) for item in failed_components[:2]))
    elif isinstance(failed_commands, list) and failed_commands:
        parts.append(f"failedCmd={len(failed_commands)}")
    return " ".join(parts)


def affected_component_execution_badge(state: dict[str, object]) -> str:
    admission = state.get("affected_component_execution_admission")
    if not isinstance(admission, dict) or not admission:
        return "N/A"
    result = str(admission.get("result") or "N/A")
    required_components = admission.get("required_components")
    missing_components = admission.get("missing_components")
    failed_components = admission.get("failed_components")
    parts = [result]
    if isinstance(required_components, list) and required_components:
        parts.append(f"components={len(required_components)}")
    if isinstance(failed_components, list) and failed_components:
        parts.append("failed@" + ",".join(str(item) for item in failed_components[:2]))
    if isinstance(missing_components, list) and missing_components:
        parts.append("missing@" + ",".join(str(item) for item in missing_components[:2]))
    return " ".join(parts)


def gate5_admission_summary_badge(state: dict[str, object]) -> str:
    summary = state.get("gate5_admission_summary")
    if not isinstance(summary, dict) or not summary:
        return "N/A"
    result = str(summary.get("result") or "N/A")
    failing = summary.get("failing_admissions")
    warning = summary.get("warning_admissions")
    parts = [result]
    if isinstance(failing, list) and failing:
        parts.append("fail=" + ",".join(str(item) for item in failing[:3]))
    if isinstance(warning, list) and warning:
        parts.append("warn=" + ",".join(str(item) for item in warning[:3]))
    return " ".join(parts)


def gate3_ai_review_badge(state: dict[str, object]) -> str:
    review = state.get("gate3_ai_review")
    if not isinstance(review, dict) or not review:
        return "N/A"
    result = str(review.get("result") or "N/A")
    mode = str(review.get("mode") or "").strip()
    confidence = str(review.get("confidence") or "").strip()
    parts = [result]
    if mode:
        parts.append(mode)
    if confidence:
        parts.append(confidence)
    return " ".join(parts)


def gate_cache_badge(state: dict[str, object]) -> str:
    gate_cache = state.get("gate_cache")
    if not isinstance(gate_cache, dict) or not gate_cache:
        return "N/A"
    parts: list[str] = []
    for gate_name in ("gate1", "gate2", "gate3", "gate4", "gate5"):
        entry = gate_cache.get(gate_name)
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "").strip()
        if not status:
            continue
        parts.append(f"{gate_name}={status}")
    return ", ".join(parts) if parts else "N/A"


def resource_claim_badges(state: dict[str, object]) -> str:
    claim_brief = state.get("design_resource_claim_brief")
    if not isinstance(claim_brief, dict):
        return "N/A"
    parts: list[str] = []
    counts_by_kind = claim_brief.get("counts_by_kind")
    if isinstance(counts_by_kind, dict):
        operation_count = counts_by_kind.get("operation")
        schema_table_count = counts_by_kind.get("schema-table")
        if isinstance(operation_count, int) and operation_count > 0:
            parts.append(f"op={operation_count}")
        if isinstance(schema_table_count, int) and schema_table_count > 0:
            parts.append(f"table={schema_table_count}")
    operation_components = claim_brief.get("operation_components")
    if isinstance(operation_components, list) and operation_components:
        parts.append("op@" + ",".join(str(item) for item in operation_components[:2]))
    schema_components = claim_brief.get("schema_table_components")
    if isinstance(schema_components, list) and schema_components:
        parts.append("tbl@" + ",".join(str(item) for item in schema_components[:2]))
    return ", ".join(parts) if parts else "N/A"


def release_exception_badges(state: dict[str, object]) -> str:
    metadata = state.get("release_exception_metadata")
    if not isinstance(metadata, dict) or not metadata.get("enabled"):
        return "N/A"
    status = str(metadata.get("status") or "ACTIVE")
    waived_checks = metadata.get("waived_checks")
    if isinstance(waived_checks, list) and waived_checks:
        return f"{status} ({', '.join(str(item) for item in waived_checks[:2])})"
    return status


def resolution_preview(state: dict[str, object], *, compact: bool = False) -> str:
    parts: list[str] = []
    missing_method_details = state.get("implementation_missing_method_details")
    if isinstance(missing_method_details, list) and missing_method_details:
        first = missing_method_details[0]
        if isinstance(first, dict):
            class_name = str(first.get("class_name") or "")
            signature = str(first.get("expected_signature") or "")
            resource_key = str(first.get("resource_key") or "")
            preview = ".".join(item for item in (class_name, signature) if item)
            if resource_key and not compact:
                preview = f"{preview} @ {resource_key}"
            if preview:
                parts.append(f"missing={preview}")
    ambiguous_classes = state.get("implementation_ambiguous_classes")
    if isinstance(ambiguous_classes, list) and ambiguous_classes:
        first = ambiguous_classes[0]
        if isinstance(first, dict):
            class_name = str(first.get("class_name") or "")
            components = first.get("candidate_components")
            if class_name:
                suffix = ""
                if not compact and isinstance(components, list) and components:
                    suffix = " @ " + ",".join(str(item) for item in components[:2])
                parts.append(f"ambiguousClass={class_name}{suffix}")
    table_brief = state.get("schema_table_resolution_brief")
    if isinstance(table_brief, dict) and table_brief.get("ambiguous_count"):
        table_name = str(table_brief.get("first_ambiguous_table") or "")
        components = table_brief.get("first_ambiguous_table_components")
        if table_name:
            suffix = ""
            if not compact and isinstance(components, list) and components:
                suffix = " @ " + ",".join(str(item) for item in components[:2])
            parts.append(f"ambiguousTable={table_name}{suffix}")
    release_exception = state.get("release_exception_metadata")
    if isinstance(release_exception, dict) and release_exception.get("enabled"):
        if compact:
            parts.append(f"releaseException={release_exception.get('status', 'ACTIVE')}")
        else:
            waived_checks = release_exception.get("waived_checks")
            checks_preview = ",".join(str(item) for item in waived_checks[:2]) if isinstance(waived_checks, list) and waived_checks else ""
            suffix = f" ({checks_preview})" if checks_preview else ""
            parts.append(f"releaseException={release_exception.get('status', 'ACTIVE')}{suffix}")
    return "; ".join(parts) if parts else "N/A"


def workspace_summary_lines(workspace: dict[str, object] | None) -> list[str]:
    payload = workspace or {}
    profiles = payload.get("profiles", [])
    profile_count = len(profiles) if isinstance(profiles, list) else 0
    return [
        f"- Active Profile: `{payload.get('active_profile', 'N/A')}`",
        f"- Active Project ID: `{payload.get('active_project_id', 'N/A')}`",
        f"- Profile Count: `{profile_count}`",
    ]

