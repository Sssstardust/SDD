#!/usr/bin/env python3
"""
Helpers for feature flow state normalization and summary assembly.
"""

from __future__ import annotations

import re
from pathlib import Path


def base_state(feature_dir: Path) -> dict[str, object]:
    return {
        "feature_dir": str(feature_dir),
        "feature_name": feature_dir.name,
        "current_stage": None,
        "risk_tier": None,
        "strict_recommended": False,
        "strict_next_step": False,
        "strict_summary": {},
        "design_version": None,
        "reports_dir": None,
        "approval_status": None,
        "gate2_result": None,
        "gate3_result": None,
        "gate4_result": None,
        "gate5_result": None,
        "implementation_result": None,
        "release_gate_result": None,
        "release_exception_metadata": {},
        "next_command": None,
        "reason": None,
        "missing_artifacts": [],
        "blockers": [],
        "implementation_framework_evidence": {},
        "implementation_match_highlights": [],
        "implementation_missing_method_details": [],
        "implementation_ambiguous_classes": [],
        "real_test_req_admission": {},
        "attached_execution_admission": {},
        "affected_component_execution_admission": {},
        "gate5_admission_summary": {},
        "gate3_rule_evaluation": {},
        "gate3_ai_review": {},
        "design_class_resolution_brief": {},
        "schema_table_resolution_brief": {},
        "design_resource_claim_summary": {},
        "design_resource_claim_brief": {},
        "gate_cache": {},
    }


def normalize_feature_state_payload(feature_dir: Path, raw_state: object, state_keys: tuple[str, ...]) -> dict[str, object]:
    state = base_state(feature_dir)
    if not isinstance(raw_state, dict):
        return state

    for key in state_keys:
        if key in raw_state:
            state[key] = raw_state[key]

    state["feature_dir"] = str(feature_dir)
    if not state.get("feature_name"):
        state["feature_name"] = feature_dir.name
    if not isinstance(state.get("missing_artifacts"), list):
        state["missing_artifacts"] = []
    if not isinstance(state.get("blockers"), list):
        state["blockers"] = []
    if not isinstance(state.get("release_exception_metadata"), dict):
        state["release_exception_metadata"] = {}
    if not isinstance(state.get("implementation_framework_evidence"), dict):
        state["implementation_framework_evidence"] = {}
    if not isinstance(state.get("implementation_match_highlights"), list):
        state["implementation_match_highlights"] = []
    if not isinstance(state.get("implementation_missing_method_details"), list):
        state["implementation_missing_method_details"] = []
    if not isinstance(state.get("implementation_ambiguous_classes"), list):
        state["implementation_ambiguous_classes"] = []
    if not isinstance(state.get("real_test_req_admission"), dict):
        state["real_test_req_admission"] = {}
    if not isinstance(state.get("attached_execution_admission"), dict):
        state["attached_execution_admission"] = {}
    if not isinstance(state.get("affected_component_execution_admission"), dict):
        state["affected_component_execution_admission"] = {}
    if not isinstance(state.get("gate5_admission_summary"), dict):
        state["gate5_admission_summary"] = {}
    if not isinstance(state.get("gate3_rule_evaluation"), dict):
        state["gate3_rule_evaluation"] = {}
    if not isinstance(state.get("gate3_ai_review"), dict):
        state["gate3_ai_review"] = {}
    if not isinstance(state.get("design_class_resolution_brief"), dict):
        state["design_class_resolution_brief"] = {}
    if not isinstance(state.get("schema_table_resolution_brief"), dict):
        state["schema_table_resolution_brief"] = {}
    if not isinstance(state.get("design_resource_claim_summary"), dict):
        state["design_resource_claim_summary"] = {}
    if not isinstance(state.get("design_resource_claim_brief"), dict):
        state["design_resource_claim_brief"] = {}
    if not isinstance(state.get("gate_cache"), dict):
        state["gate_cache"] = {}
    if not isinstance(state.get("strict_summary"), dict):
        state["strict_summary"] = {}
    return state


def build_design_resource_claim_brief(summary: object) -> dict[str, object]:
    if not isinstance(summary, dict):
        return {}
    counts = summary.get("counts_by_kind")
    components = summary.get("component_ids_by_kind")
    resource_keys = summary.get("resource_keys_by_kind")
    if not isinstance(counts, dict):
        counts = {}
    if not isinstance(components, dict):
        components = {}
    if not isinstance(resource_keys, dict):
        resource_keys = {}
    operation_components = components.get("operation", []) if isinstance(components.get("operation"), list) else []
    schema_components = components.get("schema-table", []) if isinstance(components.get("schema-table"), list) else []
    operation_keys = resource_keys.get("operation", []) if isinstance(resource_keys.get("operation"), list) else []
    schema_keys = resource_keys.get("schema-table", []) if isinstance(resource_keys.get("schema-table"), list) else []
    return {
        "counts_by_kind": counts,
        "operation_components": operation_components,
        "schema_table_components": schema_components,
        "operation_resource_keys": operation_keys[:3],
        "schema_table_resource_keys": schema_keys[:3],
    }


def build_class_resolution_brief(summary: object) -> dict[str, object]:
    if not isinstance(summary, dict):
        return {}
    ambiguous = summary.get("ambiguous_classes")
    first = ambiguous[0] if isinstance(ambiguous, list) and ambiguous else {}
    if not isinstance(first, dict):
        first = {}
    return {
        "resolved_count": len(summary.get("resolved_classes", [])) if isinstance(summary.get("resolved_classes"), list) else 0,
        "missing_count": len(summary.get("missing_classes", [])) if isinstance(summary.get("missing_classes"), list) else 0,
        "ambiguous_count": len(ambiguous) if isinstance(ambiguous, list) else 0,
        "first_ambiguous_class": first.get("class_name"),
        "first_ambiguous_class_components": first.get("candidate_components", []),
        "first_ambiguous_class_resource_keys": first.get("candidate_resource_keys", []),
    }


def build_schema_table_resolution_brief(summary: object) -> dict[str, object]:
    if not isinstance(summary, dict):
        return {}
    ambiguous = summary.get("ambiguous_tables")
    first = ambiguous[0] if isinstance(ambiguous, list) and ambiguous else {}
    if not isinstance(first, dict):
        first = {}
    return {
        "resolved_count": len(summary.get("resolved_tables", [])) if isinstance(summary.get("resolved_tables"), list) else 0,
        "missing_count": len(summary.get("missing_tables", [])) if isinstance(summary.get("missing_tables"), list) else 0,
        "ambiguous_count": len(ambiguous) if isinstance(ambiguous, list) else 0,
        "first_ambiguous_table": first.get("table_name"),
        "first_ambiguous_table_components": first.get("candidate_components", []),
        "first_ambiguous_table_resource_keys": first.get("candidate_resource_keys", []),
    }


def extract_yaml_blocks(text: str) -> list[str]:
    matches = re.findall(r"```yaml\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return matches if matches else [text]


def extract_scalar(yaml_text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", yaml_text)
    if not match:
        return None
    return match.group(1).strip().strip('"').strip("'")


def format_next_command(command: str, feature_dir: Path, *, strict: bool = False) -> str:
    suffix = " --strict" if strict else ""
    return f"python scripts/run_pipeline.py {command} {feature_dir}{suffix}"


def command_requires_strict(command: object) -> bool:
    return isinstance(command, str) and "--strict" in command.split()


def build_strict_summary(state: dict[str, object]) -> dict[str, object]:
    next_command = state.get("next_command")
    strict_next_step = bool(state.get("strict_next_step"))
    strict_recommended = bool(state.get("strict_recommended"))
    return {
        "recommended": strict_recommended,
        "next_step_strict": strict_next_step,
        "next_command_has_strict_flag": command_requires_strict(next_command),
        "mode": "strict" if strict_next_step else "recommended" if strict_recommended else "no",
    }

