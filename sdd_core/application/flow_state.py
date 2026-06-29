#!/usr/bin/env python3
"""
Compute and persist feature flow state snapshots.
"""

from __future__ import annotations

from typing import Any

from pathlib import Path

from sdd_core.domain.feature_brief import FeatureBrief
from sdd_core.domain.flow_state import FlowStateSnapshot
from sdd_core.infrastructure.json_io import read_json, write_json
from sdd_core.infrastructure.versioning import detect_latest_design_path, reports_dir_for_design
from sdd_core.application.preflight import missing_feature_prerequisites
from .flow_state_helpers import (
    base_state,
    build_class_resolution_brief,
    build_design_resource_claim_brief,
    build_schema_table_resolution_brief,
    build_strict_summary,
    command_requires_strict,
    format_next_command,
    normalize_feature_state_payload,
)


BOOTSTRAP_FILES = (
    "架构宪法.md",
    "架构设计.md",
    "模块布局.md",
    "启动计划.md",
    "scaffold-report.json",
)

STATE_KEYS = (
    "feature_dir",
    "feature_name",
    "current_stage",
    "risk_tier",
    "strict_recommended",
    "strict_next_step",
    "strict_summary",
    "design_version",
    "reports_dir",
    "approval_status",
    "gate2_result",
    "gate3_result",
    "gate4_result",
    "gate5_result",
    "implementation_result",
    "release_gate_result",
    "release_exception_metadata",
    "next_command",
    "reason",
    "missing_artifacts",
    "blockers",
    "implementation_framework_evidence",
    "implementation_match_highlights",
    "implementation_missing_method_details",
    "implementation_ambiguous_classes",
    "real_test_req_admission",
    "attached_execution_admission",
    "affected_component_execution_admission",
    "gate5_admission_summary",
    "gate3_rule_evaluation",
    "gate3_ai_review",
    "design_class_resolution_brief",
    "schema_table_resolution_brief",
    "design_resource_claim_summary",
    "design_resource_claim_brief",
    "gate_cache",
)

STATE_SOURCE_PERSISTED = "project-state.json"
STATE_SOURCE_COMPUTED_FALLBACK = "computed-fallback"
STATE_SOURCE_COMPUTED_LIVE = "computed-live"


def normalize_feature_state(feature_dir: Path, raw_state: object) -> dict[str, Any]:
    normalized = normalize_feature_state_payload(feature_dir, raw_state, STATE_KEYS)
    return FlowStateSnapshot.from_payload(feature_dir, normalized, allowed_keys=STATE_KEYS).to_payload()


def project_state_path(feature_dir: Path) -> Path:
    return feature_dir / "project-state.json"


def load_project_state(feature_dir: Path) -> dict[str, Any] | None:
    path = project_state_path(feature_dir)
    if not path.exists():
        return None
    return normalize_feature_state(feature_dir, read_json(path))


def write_project_state(feature_dir: Path, state: dict[str, Any]) -> Path:
    path = project_state_path(feature_dir)
    write_json(path, normalize_feature_state(feature_dir, state))
    return path


def build_feature_state_record(feature_dir: Path, *, prefer_persisted: bool = True) -> dict[str, Any]:
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


def _build_stage_result(
    state: dict[str, Any],
    stage: str,
    reason: str,
    next_cmd_type: str | None,
    feature_dir: Path,
    strict_recommended: bool,
) -> dict[str, Any]:
    state["current_stage"] = stage
    if next_cmd_type == "build-approval-summary":
        state["next_command"] = f"python sdd_core/run_pipeline.py build-approval-summary {feature_dir}"
    elif next_cmd_type:
        state["next_command"] = format_next_command(next_cmd_type, feature_dir, strict=strict_recommended)
    else:
        state["next_command"] = None
    state["strict_next_step"] = command_requires_strict(state["next_command"]) if state["next_command"] else False
    state["reason"] = reason
    state["strict_summary"] = build_strict_summary(state)
    return state


def _parse_gate_report(state: dict[str, Any], reports_dir: Path) -> None:
    gate_report_path = reports_dir / "gate-report.json"
    if not gate_report_path.exists():
        state["missing_artifacts"].append(str(gate_report_path))
        return

    gate_report = read_json(gate_report_path)
    if not isinstance(gate_report, dict):
        return

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
            if gate_name == "release_gate":
                exception_metadata = gate.get("release_exception_metadata")
                if isinstance(exception_metadata, dict):
                    state["release_exception_metadata"] = exception_metadata

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


def _parse_verify_report(state: dict[str, Any], reports_dir: Path) -> Any:
    verify_path = reports_dir / "verify-report.json"
    if not verify_path.exists():
        state["missing_artifacts"].append(str(verify_path))
        state["blockers"].append(f"missing implementation verification report: {verify_path}")
        return None

    verify = read_json(verify_path)
    if not isinstance(verify, dict):
        return None

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
    real_test_req_admission = verify.get("real_test_req_admission")
    if isinstance(real_test_req_admission, dict):
        state["real_test_req_admission"] = real_test_req_admission
    attached_execution_admission = verify.get("attached_execution_admission")
    if isinstance(attached_execution_admission, dict):
        state["attached_execution_admission"] = attached_execution_admission
    component_execution_admission = verify.get("affected_component_execution_admission")
    if isinstance(component_execution_admission, dict):
        state["affected_component_execution_admission"] = component_execution_admission
    gate5_admission_summary = verify.get("gate5_admission_summary")
    if isinstance(gate5_admission_summary, dict):
        state["gate5_admission_summary"] = gate5_admission_summary

    gate_report_path = reports_dir / "gate-report.json"
    gate_report = read_json(gate_report_path) if gate_report_path.exists() else None
    if isinstance(gate_report, dict):
        gate3_rule_evaluation = gate_report.get("gate3", {}).get("rule_evaluation") if isinstance(gate_report.get("gate3"), dict) else None  # type: ignore
        if isinstance(gate3_rule_evaluation, dict):
            state["gate3_rule_evaluation"] = gate3_rule_evaluation
        gate3_ai_review = gate_report.get("gate3", {}).get("ai_review") if isinstance(gate_report.get("gate3"), dict) else None  # type: ignore
        if isinstance(gate3_ai_review, dict):
            state["gate3_ai_review"] = gate3_ai_review

    execution = verify.get("execution")
    if isinstance(execution, dict) and execution.get("status") == "FAIL":
        state["blockers"].append("gate5: execution phase failed")
    implementation_result = verify.get("implementation_result")
    if implementation_result and implementation_result != "PASS":
        state["blockers"].append(f"gate5: implementation traceability={implementation_result}")
    admission = state.get("real_test_req_admission")
    if isinstance(admission, dict):
        admission_result = admission.get("result")
        if admission_result and admission_result != "PASS":
            state["blockers"].append(f"gate5: real-test admission={admission_result}")
    attached_admission = state.get("attached_execution_admission")
    if isinstance(attached_admission, dict):
        attached_result = attached_admission.get("result")
        if attached_result and attached_result not in {"PASS", "SKIPPED"}:
            state["blockers"].append(f"gate5: attached-execution admission={attached_result}")
    component_admission = state.get("affected_component_execution_admission")
    if isinstance(component_admission, dict):
        component_result = component_admission.get("result")
        if component_result and component_result != "PASS":
            state["blockers"].append(f"gate5: affected-component execution={component_result}")

    return verify_result


def _determine_current_stage(
    state: dict[str, Any],
    verify_result: Any,
    strict_recommended: bool,
    feature_dir: Path,
) -> dict[str, Any]:
    risk_high = state["risk_tier"] == "high"

    if state["gate2_result"] is None or state["gate3_result"] is None:
        return _build_stage_result(state, "design-in-progress", "design-stage gates are not fully complete", "design-cycle", feature_dir, strict_recommended)

    if risk_high and state["approval_status"] != "APPROVED":
        return _build_stage_result(state, "awaiting-approval", "high-risk design is still waiting for approval", "build-approval-summary", feature_dir, strict_recommended)

    if state["gate4_result"] == "FAIL" or state["gate5_result"] == "FAIL":
        return _build_stage_result(state, "implementation-needs-attention", "implementation-stage gates contain failures", "approved-implementation-cycle", feature_dir, strict_recommended)

    if verify_result is None:
        return _build_stage_result(state, "approved-ready-for-implementation", "design stage is complete, but implementation verification has not started", "approved-implementation-cycle", feature_dir, strict_recommended)

    if verify_result == "PASS" and state["release_gate_result"] != "PASS":
        return _build_stage_result(state, "verified-ready-for-release", "implementation verification passed, but release governance is not finished", "release-gate", feature_dir, strict_recommended)

    if verify_result == "PASS":
        return _build_stage_result(state, "release-ready", "feature passed implementation verification and release governance", None, feature_dir, strict_recommended)

    return _build_stage_result(state, "implementation-needs-attention", "implementation stage still has unresolved items", "approved-implementation-cycle", feature_dir, strict_recommended)


def compute_feature_state(feature_dir: Path) -> dict[str, Any]:
    state = base_state(feature_dir)

    prerequisite_messages = missing_feature_prerequisites(
        feature_dir,
        require_feature_brief=False,
        require_design=False,
        require_approval=False,
        require_task_slices_manifest=False,
        require_task_slice_files=False,
    )
    if prerequisite_messages:
        state["blockers"].extend(prerequisite_messages)

    feature_brief = feature_dir / "需求规格.md"
    if not feature_brief.exists():
        state["missing_artifacts"] = ["需求规格.md"]
        state["current_stage"] = "uninitialized"
        state["next_command"] = f"python sdd_core/run_pipeline.py init-feature {feature_dir.name}"
        state["reason"] = "missing 需求规格.md"
        return state

    feature_text = feature_brief.read_text(encoding="utf-8")
    brief = FeatureBrief.from_text(feature_text, feature_dir_name=feature_dir.name)
    state["feature_name"] = brief.feature_name
    state["risk_tier"] = brief.risk_tier
    project_mode = brief.project_mode
    strict_recommended = state["risk_tier"] == "high"
    state["strict_recommended"] = strict_recommended

    design_path = detect_latest_design_path(feature_dir)
    if project_mode == "greenfield":
        missing_bootstrap = [name for name in BOOTSTRAP_FILES if not (feature_dir / name).exists()]
        if missing_bootstrap:
            state["missing_artifacts"] = missing_bootstrap
            state["current_stage"] = "bootstrap-needed"
            state["next_command"] = f"python sdd_core/run_pipeline.py bootstrap {feature_dir}"
            state["reason"] = "greenfield feature is missing bootstrap artifacts"
            return state

    if not design_path.exists():
        state["missing_artifacts"] = ["design-v{N}.md"]
        state["current_stage"] = "feature-brief-ready"
        state["next_command"] = format_next_command("design-cycle", feature_dir, strict=strict_recommended)
        state["strict_next_step"] = command_requires_strict(state["next_command"])
        state["reason"] = "design-v{N}.md has not been generated yet"
        state["strict_summary"] = build_strict_summary(state)
        return state

    state["design_version"] = design_path.name
    reports_dir = reports_dir_for_design(feature_dir, design_path)
    state["reports_dir"] = str(reports_dir)

    _parse_gate_report(state, reports_dir)

    approval_path = reports_dir / "approval.json"
    if approval_path.exists():
        approval = read_json(approval_path)
        if isinstance(approval, dict):
            state["approval_status"] = approval.get("status")
    elif state["risk_tier"] == "high":
        state["missing_artifacts"].append(str(approval_path))
        state["blockers"].append(f"missing approval prerequisite: {approval_path}")

    verify_result = _parse_verify_report(state, reports_dir)

    gate4_path = reports_dir / "gate4-skeleton.json"
    if not gate4_path.exists():
        state["missing_artifacts"].append(str(gate4_path))
        state["blockers"].append(f"missing gate4 skeleton report: {gate4_path}")

    task_slices_manifest = feature_dir / "tasks" / "task-slices.generated.json"
    if not task_slices_manifest.exists():
        state["missing_artifacts"].append(str(task_slices_manifest))
        state["blockers"].append(f"missing task slices manifest: {task_slices_manifest}")

    return _determine_current_stage(state, verify_result, strict_recommended, feature_dir)


def inspect_feature_state(feature_dir: Path, *, prefer_persisted: bool = True) -> dict[str, Any]:
    return build_feature_state_record(feature_dir, prefer_persisted=prefer_persisted)
