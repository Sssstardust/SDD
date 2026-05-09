#!/usr/bin/env python3
"""
flow_state.py

Compute and persist feature flow state snapshots.
"""

from __future__ import annotations

import re
from pathlib import Path

from json_io import read_json, write_json
from versioning import detect_latest_design_path, reports_dir_for_design


BOOTSTRAP_FILES = (
    "constitution.md",
    "architecture.md",
    "module-layout.md",
    "bootstrap-plan.md",
    "scaffold-report.json",
)

STATE_KEYS = (
    "feature_dir",
    "feature_name",
    "current_stage",
    "risk_tier",
    "design_version",
    "reports_dir",
    "approval_status",
    "gate2_result",
    "gate3_result",
    "gate4_result",
    "gate5_result",
    "implementation_result",
    "release_gate_result",
    "next_command",
    "reason",
    "missing_artifacts",
    "blockers",
    "implementation_framework_evidence",
    "implementation_match_highlights",
    "implementation_missing_method_details",
    "implementation_ambiguous_classes",
    "design_class_resolution_brief",
    "schema_table_resolution_brief",
    "design_resource_claim_summary",
    "design_resource_claim_brief",
)

STATE_SOURCE_PERSISTED = "project-state.json"
STATE_SOURCE_COMPUTED_FALLBACK = "computed-fallback"
STATE_SOURCE_COMPUTED_LIVE = "computed-live"


def _base_state(feature_dir: Path) -> dict[str, object]:
    return {
        "feature_dir": str(feature_dir),
        "feature_name": feature_dir.name,
        "current_stage": None,
        "risk_tier": None,
        "design_version": None,
        "reports_dir": None,
        "approval_status": None,
        "gate2_result": None,
        "gate3_result": None,
        "gate4_result": None,
        "gate5_result": None,
        "implementation_result": None,
        "release_gate_result": None,
        "next_command": None,
        "reason": None,
        "missing_artifacts": [],
        "blockers": [],
        "implementation_framework_evidence": {},
        "implementation_match_highlights": [],
        "implementation_missing_method_details": [],
        "implementation_ambiguous_classes": [],
        "design_class_resolution_brief": {},
        "schema_table_resolution_brief": {},
        "design_resource_claim_summary": {},
        "design_resource_claim_brief": {},
    }


def normalize_feature_state(feature_dir: Path, raw_state: object) -> dict[str, object]:
    state = _base_state(feature_dir)
    if not isinstance(raw_state, dict):
        return state

    for key in STATE_KEYS:
        if key in raw_state:
            state[key] = raw_state[key]

    state["feature_dir"] = str(feature_dir)
    if not state.get("feature_name"):
        state["feature_name"] = feature_dir.name
    if not isinstance(state.get("missing_artifacts"), list):
        state["missing_artifacts"] = []
    if not isinstance(state.get("blockers"), list):
        state["blockers"] = []
    if not isinstance(state.get("implementation_framework_evidence"), dict):
        state["implementation_framework_evidence"] = {}
    if not isinstance(state.get("implementation_match_highlights"), list):
        state["implementation_match_highlights"] = []
    if not isinstance(state.get("implementation_missing_method_details"), list):
        state["implementation_missing_method_details"] = []
    if not isinstance(state.get("implementation_ambiguous_classes"), list):
        state["implementation_ambiguous_classes"] = []
    if not isinstance(state.get("design_class_resolution_brief"), dict):
        state["design_class_resolution_brief"] = {}
    if not isinstance(state.get("schema_table_resolution_brief"), dict):
        state["schema_table_resolution_brief"] = {}
    if not isinstance(state.get("design_resource_claim_summary"), dict):
        state["design_resource_claim_summary"] = {}
    if not isinstance(state.get("design_resource_claim_brief"), dict):
        state["design_resource_claim_brief"] = {}
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


def project_state_path(feature_dir: Path) -> Path:
    return feature_dir / "project-state.json"


def load_project_state(feature_dir: Path) -> dict[str, object] | None:
    path = project_state_path(feature_dir)
    if not path.exists():
        return None
    return normalize_feature_state(feature_dir, read_json(path))


def write_project_state(feature_dir: Path, state: dict[str, object]) -> Path:
    path = project_state_path(feature_dir)
    write_json(path, normalize_feature_state(feature_dir, state))
    return path


def build_feature_state_record(feature_dir: Path, *, prefer_persisted: bool = True) -> dict[str, object]:
    path = project_state_path(feature_dir)
    path_exists = path.exists()

    if prefer_persisted:
        persisted = load_project_state(feature_dir)
        if persisted is not None:
            state = dict(persisted)
            state_source = STATE_SOURCE_PERSISTED
        else:
            state = compute_feature_state(feature_dir)
            state_source = STATE_SOURCE_COMPUTED_FALLBACK
    else:
        state = compute_feature_state(feature_dir)
        state_source = STATE_SOURCE_COMPUTED_LIVE

    state["state_source"] = state_source
    state["project_state_path"] = str(path)
    state["project_state_exists"] = path_exists
    return state


def compute_feature_state(feature_dir: Path) -> dict[str, object]:
    state = _base_state(feature_dir)

    feature_brief = feature_dir / "feature-brief.md"
    if not feature_brief.exists():
        state["missing_artifacts"] = ["feature-brief.md"]
        state["current_stage"] = "uninitialized"
        state["next_command"] = f"python scripts/run_pipeline.py init-feature {feature_dir.name}"
        state["reason"] = "missing feature-brief.md"
        return state

    feature_text = feature_brief.read_text(encoding="utf-8")
    yaml_text = "\n".join(extract_yaml_blocks(feature_text))
    state["feature_name"] = extract_scalar(yaml_text, "feature_name") or feature_dir.name
    state["risk_tier"] = extract_scalar(yaml_text, "risk_tier") or "low"
    project_mode = extract_scalar(yaml_text, "project_mode") or "brownfield"
    strict_recommended = state["risk_tier"] == "high"

    design_path = detect_latest_design_path(feature_dir)
    if project_mode == "greenfield":
        missing_bootstrap = [name for name in BOOTSTRAP_FILES if not (feature_dir / name).exists()]
        if missing_bootstrap:
            state["missing_artifacts"] = missing_bootstrap
            state["current_stage"] = "bootstrap-needed"
            state["next_command"] = f"python scripts/run_pipeline.py bootstrap {feature_dir}"
            state["reason"] = "greenfield feature is missing bootstrap artifacts"
            return state

    if not design_path.exists():
        state["missing_artifacts"] = ["design-v{N}.md"]
        state["current_stage"] = "feature-brief-ready"
        state["next_command"] = format_next_command("design-cycle", feature_dir, strict=strict_recommended)
        state["reason"] = "design-v{N}.md has not been generated yet"
        return state

    state["design_version"] = design_path.name
    reports_dir = reports_dir_for_design(feature_dir, design_path)
    state["reports_dir"] = str(reports_dir)

    gate_report_path = reports_dir / "gate-report.json"
    if gate_report_path.exists():
        gate_report = read_json(gate_report_path)
        if isinstance(gate_report, dict):
            for gate_name in ("gate2", "gate3", "gate4", "gate5", "release_gate"):
                gate = gate_report.get(gate_name)
                if isinstance(gate, dict):
                    state[f"{gate_name}_result"] = gate.get("result")
                    warnings = gate.get("warnings", [])
                    if isinstance(warnings, list):
                        state["blockers"].extend(f"{gate_name}: {warning}" for warning in warnings)
                    errors = gate.get("errors", [])
                    if isinstance(errors, list):
                        state["blockers"].extend(f"{gate_name}: {error}" for error in errors)
            for gate_name in ("release_gate", "gate5", "gate2"):
                gate = gate_report.get(gate_name)
                if not isinstance(gate, dict):
                    continue
                summary = gate.get("design_resource_claim_summary")
                if isinstance(summary, dict):
                    state["design_resource_claim_summary"] = summary
                    state["design_resource_claim_brief"] = build_design_resource_claim_brief(summary)
                if gate_name == "gate2":
                    truthfulness_report = gate.get("truthfulness_report")
                    if isinstance(truthfulness_report, dict):
                        evidence = truthfulness_report.get("evidence")
                        if isinstance(evidence, dict):
                            module_map_evidence = evidence.get("module_map")
                            if isinstance(module_map_evidence, dict):
                                class_resolution = module_map_evidence.get("class_resolution")
                                if isinstance(class_resolution, dict):
                                    state["design_class_resolution_brief"] = build_class_resolution_brief(class_resolution)
                            schema_context_evidence = evidence.get("schema_context")
                            if isinstance(schema_context_evidence, dict):
                                table_resolution = schema_context_evidence.get("table_resolution")
                                if isinstance(table_resolution, dict):
                                    state["schema_table_resolution_brief"] = build_schema_table_resolution_brief(table_resolution)
                if state.get("design_resource_claim_summary"):
                    break
    else:
        state["missing_artifacts"].append(str(gate_report_path))

    approval_path = reports_dir / "approval.json"
    if approval_path.exists():
        approval = read_json(approval_path)
        if isinstance(approval, dict):
            state["approval_status"] = approval.get("status")
    elif state["risk_tier"] == "high":
        state["missing_artifacts"].append(str(approval_path))

    verify_path = reports_dir / "verify-report.json"
    verify_result = None
    if verify_path.exists():
        verify = read_json(verify_path)
        if isinstance(verify, dict):
            verify_result = verify.get("result")
            state["gate5_result"] = verify_result
            state["implementation_result"] = verify.get("implementation_result")
            framework_evidence = verify.get("implementation_method_framework_evidence")
            if isinstance(framework_evidence, dict):
                state["implementation_framework_evidence"] = framework_evidence
            match_highlights = verify.get("implementation_method_match_highlights")
            if isinstance(match_highlights, list):
                state["implementation_match_highlights"] = match_highlights
            missing_method_details = verify.get("implementation_missing_method_details")
            if isinstance(missing_method_details, list):
                state["implementation_missing_method_details"] = missing_method_details
            ambiguous_classes = verify.get("implementation_ambiguous_classes")
            if isinstance(ambiguous_classes, list):
                state["implementation_ambiguous_classes"] = ambiguous_classes
            execution = verify.get("execution")
            if isinstance(execution, dict) and execution.get("status") == "FAIL":
                state["blockers"].append("gate5: execution phase failed")
            implementation_result = verify.get("implementation_result")
            if implementation_result and implementation_result != "PASS":
                state["blockers"].append(f"gate5: implementation traceability={implementation_result}")
    else:
        state["missing_artifacts"].append(str(verify_path))

    gate4_path = reports_dir / "gate4-skeleton.json"
    if not gate4_path.exists():
        state["missing_artifacts"].append(str(gate4_path))

    risk_high = state["risk_tier"] == "high"

    if state["gate2_result"] is None or state["gate3_result"] is None:
        state["current_stage"] = "design-in-progress"
        state["next_command"] = format_next_command("design-cycle", feature_dir, strict=strict_recommended)
        state["reason"] = "design-stage gates are not fully complete"
        return state

    if risk_high and state["approval_status"] != "APPROVED":
        state["current_stage"] = "awaiting-approval"
        state["next_command"] = f"python scripts/run_pipeline.py build-approval-summary {feature_dir}"
        state["reason"] = "high-risk design is still waiting for approval"
        return state

    if state["gate4_result"] == "FAIL" or state["gate5_result"] == "FAIL":
        state["current_stage"] = "implementation-needs-attention"
        state["next_command"] = format_next_command(
            "approved-implementation-cycle",
            feature_dir,
            strict=strict_recommended,
        )
        state["reason"] = "implementation-stage gates contain failures"
        return state

    if verify_result is None:
        state["current_stage"] = "approved-ready-for-implementation"
        state["next_command"] = format_next_command(
            "approved-implementation-cycle",
            feature_dir,
            strict=strict_recommended,
        )
        state["reason"] = "design stage is complete, but implementation verification has not started"
        return state

    if verify_result == "PASS" and state["release_gate_result"] != "PASS":
        state["current_stage"] = "verified-ready-for-release"
        state["next_command"] = format_next_command("release-gate", feature_dir, strict=strict_recommended)
        state["reason"] = "implementation verification passed, but release governance is not finished"
        return state

    if verify_result == "PASS":
        state["current_stage"] = "release-ready"
        state["next_command"] = None
        state["reason"] = "feature passed implementation verification and release governance"
        return state

    state["current_stage"] = "implementation-needs-attention"
    state["next_command"] = format_next_command("approved-implementation-cycle", feature_dir, strict=strict_recommended)
    state["reason"] = "implementation stage still has unresolved items"
    return state


def inspect_feature_state(feature_dir: Path, *, prefer_persisted: bool = True) -> dict[str, object]:
    return build_feature_state_record(feature_dir, prefer_persisted=prefer_persisted)
