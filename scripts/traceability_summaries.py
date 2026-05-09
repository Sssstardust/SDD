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

    aliases: dict[str, list[dict[str, object]]] = {}
    for item in module_map.get("classes", []):
        if not isinstance(item, dict):
            continue
        if not matches_affected_components(item, affected_components):
            continue
        for key in ("resource_key", "fqn", "simple_name", "class_name", "display_name"):
            value = item.get(key)
            if not isinstance(value, str) or not value:
                continue
            alias = value.split("::")[-1].split(".")[-1]
            aliases.setdefault(alias, []).append(item)

    resolved_classes: set[str] = set()
    missing_classes: set[str] = set()
    ambiguous_classes: list[dict[str, object]] = []
    for class_name in participant_classes:
        candidates = aliases.get(class_name, [])
        unique_candidates = {
            str(item.get("resource_key") or item.get("fqn") or item.get("class_name") or ""): item
            for item in candidates
            if isinstance(item, dict)
        }
        if len(unique_candidates) == 1:
            resolved_classes.add(class_name)
            continue
        if len(unique_candidates) > 1:
            ambiguous_classes.append(
                {
                    "class_name": class_name,
                    "candidate_resource_keys": sorted(unique_candidates),
                    "candidate_components": sorted(
                        {
                            str(item.get("component_id") or "")
                            for item in unique_candidates.values()
                            if str(item.get("component_id") or "")
                        }
                    ),
                }
            )
            continue
        missing_classes.add(class_name)

    summary["resolved_classes"] = sorted(resolved_classes)
    summary["missing_classes"] = sorted(missing_classes)
    summary["ambiguous_classes"] = sorted(ambiguous_classes, key=lambda item: str(item.get("class_name") or ""))
    return summary


def summarize_controller_endpoint_mapping(
    openapi_operations: list[dict[str, str]],
    controller_endpoints: list[dict[str, str]],
) -> dict[str, object]:
    summary: dict[str, object] = {
        "missing": [],
        "operation_mismatches": [],
        "ambiguous": [],
    }
    endpoints_by_resource: dict[tuple[str, str], list[dict[str, str]]] = {}
    for endpoint in controller_endpoints:
        endpoints_by_resource.setdefault((endpoint["path"], endpoint["method"]), []).append(endpoint)

    missing: list[str] = []
    operation_mismatches: list[str] = []
    ambiguous: list[dict[str, object]] = []
    for operation in openapi_operations:
        path = str(operation.get("path") or "")
        method = str(operation.get("method") or "")
        operation_id = str(operation.get("operation_id") or "")
        matches = endpoints_by_resource.get((path, method), [])
        if not matches:
            missing.append(f"{method} {path}")
            continue
        unique_resources = {
            str(item.get("resource_key") or item.get("class_name") or "")
            for item in matches
            if isinstance(item, dict)
        }
        if len(unique_resources) > 1:
            ambiguous.append(
                {
                    "path": path,
                    "method": method,
                    "candidate_resource_keys": sorted(unique_resources),
                    "candidate_components": sorted(
                        {
                            str(item.get("component_id") or "")
                            for item in matches
                            if isinstance(item, dict) and str(item.get("component_id") or "")
                        }
                    ),
                }
            )
        if operation_id:
            candidate_ids = {str(item.get("operation_id") or item.get("method_name") or "") for item in matches}
            if operation_id not in candidate_ids:
                operation_mismatches.append(f"{method} {path}: openapi={operation_id}, controller={', '.join(sorted(candidate_ids))}")

    summary["missing"] = sorted(set(missing))
    summary["operation_mismatches"] = sorted(set(operation_mismatches))
    summary["ambiguous"] = sorted(ambiguous, key=lambda item: (str(item.get("method") or ""), str(item.get("path") or "")))
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
    summary: dict[str, object] = {
        "resolved_tables": [],
        "missing_tables": [],
        "ambiguous_tables": [],
    }
    if not isinstance(schema_context, dict) or not table_names:
        return summary

    entries = extract_schema_table_entries(schema_context, affected_components)
    resolved_tables: set[str] = set()
    missing_tables: set[str] = set()
    ambiguous_tables: list[dict[str, object]] = []

    for table_name in table_names:
        entry = resolve_schema_table_entry(entries, table_name)
        if entry:
            resolved_tables.add(table_name)
            continue
        candidates = schema_table_candidates(entries, table_name)
        if len(candidates) > 1:
            ambiguous_tables.append(
                {
                    "table_name": table_name,
                    "candidate_resource_keys": sorted(
                        {
                            str(item.get("resource_key") or item.get("table_name") or "")
                            for item in candidates
                            if isinstance(item, dict)
                        }
                    ),
                    "candidate_components": sorted(
                        {
                            str(item.get("component_id") or "")
                            for item in candidates
                            if isinstance(item, dict) and str(item.get("component_id") or "")
                        }
                    ),
                }
            )
            continue
        missing_tables.add(table_name)

    summary["resolved_tables"] = sorted(resolved_tables)
    summary["missing_tables"] = sorted(missing_tables)
    summary["ambiguous_tables"] = sorted(ambiguous_tables, key=lambda item: str(item.get("table_name") or ""))
    return summary


def summarize_method_framework_evidence(method_match_details: list[dict[str, object]]) -> dict[str, object]:
    summary = {
        "inherited_matches": 0,
        "mybatis_bound_matches": 0,
        "mybatis_result_map_matches": 0,
        "low_confidence_matches": 0,
        "lombok_inferred_matches": 0,
        "owner_classes": [],
        "inherited_from": [],
        "mybatis_statement_ids": [],
        "mybatis_result_map_ids": [],
        "low_confidence_resource_keys": [],
    }
    owner_classes: set[str] = set()
    inherited_from: set[str] = set()
    mybatis_statement_ids: set[str] = set()
    mybatis_result_map_ids: set[str] = set()
    low_confidence_resource_keys: set[str] = set()
    for item in method_match_details:
        if not isinstance(item, dict) or not item.get("matched"):
            continue
        method_detail = item.get("matched_method_detail")
        if not isinstance(method_detail, dict):
            continue
        owner_class = method_detail.get("owner_class")
        if isinstance(owner_class, str) and owner_class:
            owner_classes.add(owner_class)
        inherited_parent = method_detail.get("inherited_from")
        if isinstance(inherited_parent, str) and inherited_parent:
            inherited_from.add(inherited_parent)
            summary["inherited_matches"] += 1
        confidence = str(method_detail.get("confidence") or "").lower()
        if confidence == "low":
            summary["low_confidence_matches"] += 1
            resource_key = item.get("resource_key")
            if isinstance(resource_key, str) and resource_key:
                low_confidence_resource_keys.add(resource_key)
        if str(method_detail.get("inference_source") or "").startswith("lombok-"):
            summary["lombok_inferred_matches"] += 1
        mybatis_statement = method_detail.get("mybatis_statement")
        if isinstance(mybatis_statement, dict):
            summary["mybatis_bound_matches"] += 1
            statement_id = mybatis_statement.get("id")
            if isinstance(statement_id, str) and statement_id:
                mybatis_statement_ids.add(statement_id)
            result_map_id = mybatis_statement.get("result_map")
            if isinstance(result_map_id, str) and result_map_id:
                mybatis_result_map_ids.add(result_map_id)
                summary["mybatis_result_map_matches"] += 1
    summary["owner_classes"] = sorted(owner_classes)
    summary["inherited_from"] = sorted(inherited_from)
    summary["mybatis_statement_ids"] = sorted(mybatis_statement_ids)
    summary["mybatis_result_map_ids"] = sorted(mybatis_result_map_ids)
    summary["low_confidence_resource_keys"] = sorted(low_confidence_resource_keys)
    return summary


def build_implementation_traceability_report_fields(traceability: dict[str, object]) -> dict[str, object]:
    method_match_details = traceability.get("method_match_details")
    if not isinstance(method_match_details, list):
        method_match_details = []
    framework_evidence = traceability.get("method_framework_evidence")
    if not isinstance(framework_evidence, dict):
        framework_evidence = summarize_method_framework_evidence(method_match_details)
    match_modes = sorted(
        {
            str(item.get("match_mode"))
            for item in method_match_details
            if isinstance(item, dict) and item.get("matched") and item.get("match_mode")
        }
    )
    matched_method_highlights: list[dict[str, object]] = []
    for item in method_match_details:
        if not isinstance(item, dict) or not item.get("matched"):
            continue
        method_detail = item.get("matched_method_detail")
        if not isinstance(method_detail, dict):
            continue
        highlight = {
            "class_name": item.get("class_name"),
            "expected_signature": item.get("expected_signature"),
            "matched_signature": item.get("matched_signature"),
            "match_mode": item.get("match_mode"),
            "resource_key": item.get("resource_key"),
            "component_id": item.get("component_id"),
            "owner_class": method_detail.get("owner_class"),
            "inherited_from": method_detail.get("inherited_from"),
            "inference_source": method_detail.get("inference_source"),
            "confidence": method_detail.get("confidence"),
            "scan_reliability": item.get("scan_reliability"),
            "mybatis_statement": method_detail.get("mybatis_statement"),
        }
        if any(
            highlight.get(key)
            for key in ("owner_class", "inherited_from", "inference_source", "mybatis_statement", "scan_reliability")
        ):
            matched_method_highlights.append(highlight)
    return {
        "implementation_message": str(traceability.get("message") or ""),
        "implementation_match_modes": match_modes,
        "implementation_method_framework_evidence": framework_evidence,
        "implementation_method_match_highlights": matched_method_highlights,
        "implementation_method_match_details": method_match_details,
        "implementation_matched_methods": traceability.get("matched_methods", []),
        "implementation_missing_methods": traceability.get("missing_methods", []),
        "implementation_missing_method_details": traceability.get("missing_method_details", []),
        "implementation_ambiguous_classes": traceability.get("ambiguous_classes", []),
    }
