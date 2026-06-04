#!/usr/bin/env python3
"""
Shared summary builders for Gate 2 / Gate 5 traceability outputs.
"""

from __future__ import annotations


def summarize_design_class_reliability(
    module_map: object,
    participant_classes: list[str],
    *,
    affected_components: set[str],
    matches_affected_components,
) -> dict[str, object]:
    summary: dict[str, object] = {
        "matched_classes": [],
        "low_confidence_classes": [],
        "lombok_inferred_classes": [],
        "mybatis_bound_classes": [],
        "inherited_classes": [],
    }
    if not isinstance(module_map, dict) or not participant_classes:
        return summary

    matched_classes: set[str] = set()
    low_confidence_classes: set[str] = set()
    lombok_inferred_classes: set[str] = set()
    mybatis_bound_classes: set[str] = set()
    inherited_classes: set[str] = set()

    for item in module_map.get("classes", []):
        if not isinstance(item, dict):
            continue
        if not matches_affected_components(item, affected_components):
            continue
        aliases = {
            str(item.get(key)).split(".")[-1]
            for key in ("simple_name", "class_name", "display_name", "fqn")
            if isinstance(item.get(key), str) and item.get(key)
        }
        matched_participants = aliases & set(participant_classes)
        if not matched_participants:
            continue
        scan_reliability = item.get("scan_reliability")
        for participant in matched_participants:
            matched_classes.add(participant)
            if isinstance(scan_reliability, dict):
                class_confidence = str(scan_reliability.get("class_confidence") or "").lower()
                method_confidence = str(scan_reliability.get("method_confidence") or "").lower()
                if "low" in {class_confidence, method_confidence}:
                    low_confidence_classes.add(participant)
                evidence_sources = scan_reliability.get("evidence_sources")
                if isinstance(evidence_sources, list):
                    normalized_sources = {str(source) for source in evidence_sources}
                    if "lombok-inference" in normalized_sources:
                        lombok_inferred_classes.add(participant)
                    if "mybatis-xml" in normalized_sources:
                        mybatis_bound_classes.add(participant)
                    if "inheritance" in normalized_sources:
                        inherited_classes.add(participant)

    summary["matched_classes"] = sorted(matched_classes)
    summary["low_confidence_classes"] = sorted(low_confidence_classes)
    summary["lombok_inferred_classes"] = sorted(lombok_inferred_classes)
    summary["mybatis_bound_classes"] = sorted(mybatis_bound_classes)
    summary["inherited_classes"] = sorted(inherited_classes)
    return summary


def summarize_design_class_resolution(
    module_map: object,
    participant_classes: list[str],
    *,
    affected_components: set[str],
    matches_affected_components,
) -> dict[str, object]:
    summary: dict[str, object] = {
        "resolved_classes": [],
        "missing_classes": [],
        "ambiguous_classes": [],
    }
    if not isinstance(module_map, dict) or not participant_classes:
        return summary

    matched_participants: dict[str, list[dict[str, object]]] = {participant: [] for participant in participant_classes}
    for item in module_map.get("classes", []):
        if not isinstance(item, dict):
            continue
        if not matches_affected_components(item, affected_components):
            continue
        aliases = {
            str(item.get(key)).split(".")[-1]
            for key in ("simple_name", "class_name", "display_name", "fqn")
            if isinstance(item.get(key), str) and item.get(key)
        }
        for participant in participant_classes:
            if participant in aliases:
                matched_participants.setdefault(participant, []).append(item)

    resolved: list[str] = []
    missing: list[str] = []
    ambiguous: list[dict[str, object]] = []
    for participant in participant_classes:
        candidates = matched_participants.get(participant, [])
        if not candidates:
            missing.append(participant)
            continue
        if len(candidates) == 1:
            resolved.append(participant)
            continue
        candidate_resource_keys = sorted(
            {
                str(item.get("resource_key") or "")
                for item in candidates
                if str(item.get("resource_key") or "")
            }
        )
        candidate_components = sorted(
            {
                str(item.get("component_id") or "")
                for item in candidates
                if str(item.get("component_id") or "")
            }
        )
        ambiguous.append(
            {
                "class_name": participant,
                "candidate_resource_keys": candidate_resource_keys,
                "candidate_components": candidate_components,
            }
        )

    summary["resolved_classes"] = sorted(resolved)
    summary["missing_classes"] = sorted(missing)
    summary["ambiguous_classes"] = ambiguous
    return summary


def summarize_controller_endpoint_mapping(
    openapi_operations: list[dict[str, str]],
    controller_endpoints: list[dict[str, str]],
) -> dict[str, object]:
    summary = {
        "missing": [],
        "operation_mismatches": [],
        "ambiguous": [],
    }
    controller_index: dict[tuple[str, str], list[dict[str, str]]] = {}
    for endpoint in controller_endpoints:
        if not isinstance(endpoint, dict):
            continue
        key = (str(endpoint.get("method") or "").upper(), str(endpoint.get("path") or ""))
        controller_index.setdefault(key, []).append(endpoint)

    for operation in openapi_operations:
        if not isinstance(operation, dict):
            continue
        method = str(operation.get("method") or "").upper()
        path = str(operation.get("path") or "")
        operation_id = str(operation.get("operation_id") or "")
        candidates = controller_index.get((method, path), [])
        if not candidates:
            summary["missing"].append(f"{method} {path}")
            continue
        if len(candidates) > 1:
            summary["ambiguous"].append(
                {
                    "path": path,
                    "method": method,
                    "candidate_resource_keys": sorted(
                        {
                            str(item.get("resource_key") or "")
                            for item in candidates
                            if str(item.get("resource_key") or "")
                        }
                    ),
                    "candidate_components": sorted(
                        {
                            str(item.get("component_id") or "")
                            for item in candidates
                            if str(item.get("component_id") or "")
                        }
                    ),
                }
            )
            continue
        controller_operation_id = str(candidates[0].get("operation_id") or "")
        if operation_id and controller_operation_id and operation_id != controller_operation_id:
            summary["operation_mismatches"].append(f"{method} {path}")

    return summary


def summarize_schema_table_resolution(
    schema_context: object,
    table_names: list[str],
    *,
    affected_components: set[str],
    extract_schema_table_entries,
    resolve_schema_table_entry,
    schema_table_candidates,
) -> dict[str, object]:
    summary = {
        "resolved_tables": [],
        "missing_tables": [],
        "ambiguous_tables": [],
    }
    entries = extract_schema_table_entries(schema_context, affected_components)
    for table_name in table_names:
        resolved = resolve_schema_table_entry(entries, table_name)
        if resolved:
            summary["resolved_tables"].append(table_name)
            continue
        candidates = schema_table_candidates(entries, table_name)
        if not candidates:
            summary["missing_tables"].append(table_name)
            continue
        summary["ambiguous_tables"].append(
            {
                "table_name": table_name,
                "candidate_resource_keys": sorted(
                    {
                        str(item.get("resource_key") or "")
                        for item in candidates
                        if str(item.get("resource_key") or "")
                    }
                ),
                "candidate_components": sorted(
                    {
                        str(item.get("component_id") or "")
                        for item in candidates
                        if str(item.get("component_id") or "")
                    }
                ),
            }
        )

    summary["resolved_tables"] = sorted(summary["resolved_tables"])
    summary["missing_tables"] = sorted(summary["missing_tables"])
    return summary


def summarize_method_framework_evidence(method_match_details: list[dict[str, object]]) -> dict[str, object]:
    inherited_from: set[str] = set()
    owner_classes: set[str] = set()
    mybatis_statement_ids: set[str] = set()
    mybatis_result_map_ids: set[str] = set()
    low_confidence_resource_keys: set[str] = set()

    inherited_matches = 0
    mybatis_bound_matches = 0
    mybatis_result_map_matches = 0
    low_confidence_matches = 0
    lombok_inferred_matches = 0

    for item in method_match_details:
        if not isinstance(item, dict) or not item.get("matched"):
            continue
        scan_reliability = item.get("scan_reliability")
        if isinstance(scan_reliability, dict):
            if str(scan_reliability.get("class_confidence") or "").lower() == "low" or str(scan_reliability.get("method_confidence") or "").lower() == "low":
                low_confidence_matches += 1
                resource_key = str(item.get("resource_key") or "")
                if resource_key:
                    low_confidence_resource_keys.add(resource_key)
            evidence_sources = scan_reliability.get("evidence_sources")
            if isinstance(evidence_sources, list) and "lombok-inference" in {str(source) for source in evidence_sources}:
                lombok_inferred_matches += 1

        matched_method_detail = item.get("matched_method_detail")
        if not isinstance(matched_method_detail, dict):
            continue
        owner_class = str(matched_method_detail.get("owner_class") or "")
        inherited = str(matched_method_detail.get("inherited_from") or "")
        if owner_class:
            owner_classes.add(owner_class)
        if inherited:
            inherited_from.add(inherited)
            inherited_matches += 1
        statement = matched_method_detail.get("mybatis_statement")
        if isinstance(statement, dict):
            mybatis_bound_matches += 1
            statement_id = str(statement.get("id") or "")
            if statement_id:
                mybatis_statement_ids.add(statement_id)
            result_map = str(statement.get("result_map") or "")
            if result_map:
                mybatis_result_map_matches += 1
                mybatis_result_map_ids.add(result_map)

    return {
        "inherited_matches": inherited_matches,
        "low_confidence_matches": low_confidence_matches,
        "lombok_inferred_matches": lombok_inferred_matches,
        "mybatis_bound_matches": mybatis_bound_matches,
        "mybatis_result_map_matches": mybatis_result_map_matches,
        "low_confidence_resource_keys": sorted(low_confidence_resource_keys),
        "owner_classes": sorted(owner_classes),
        "inherited_from": sorted(inherited_from),
        "mybatis_statement_ids": sorted(mybatis_statement_ids),
        "mybatis_result_map_ids": sorted(mybatis_result_map_ids),
    }


def build_implementation_traceability_report_fields(traceability: dict[str, object]) -> dict[str, object]:
    method_match_details = traceability.get("method_match_details", [])
    if not isinstance(method_match_details, list):
        method_match_details = []
    framework_evidence = traceability.get("method_framework_evidence")
    if not isinstance(framework_evidence, dict):
        framework_evidence = summarize_method_framework_evidence(method_match_details)
    match_modes = sorted(
        {
            str(item.get("match_mode") or "")
            for item in method_match_details
            if isinstance(item, dict) and item.get("match_mode")
        }
    )
    missing_method_details = traceability.get("missing_method_details", [])
    if not isinstance(missing_method_details, list):
        missing_method_details = []
    ambiguous_classes = traceability.get("ambiguous_classes", [])
    if not isinstance(ambiguous_classes, list):
        ambiguous_classes = []
    highlights: list[dict[str, object]] = []
    for item in method_match_details:
        if not isinstance(item, dict):
            continue
        highlight = dict(item)
        matched_method_detail = item.get("matched_method_detail")
        if isinstance(matched_method_detail, dict):
            if "owner_class" in matched_method_detail:
                highlight["owner_class"] = matched_method_detail.get("owner_class")
            if "inherited_from" in matched_method_detail:
                highlight["inherited_from"] = matched_method_detail.get("inherited_from")
            if "mybatis_statement" in matched_method_detail:
                highlight["mybatis_statement"] = matched_method_detail.get("mybatis_statement")
        highlights.append(highlight)
    return {
        "implementation_match_modes": match_modes,
        "implementation_method_framework_evidence": framework_evidence,
        "implementation_method_match_highlights": highlights,
        "implementation_missing_methods": traceability.get("missing_methods", []),
        "implementation_missing_method_details": missing_method_details,
        "implementation_ambiguous_classes": ambiguous_classes,
    }
