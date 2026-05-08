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
    "release_gate_result",
    "next_command",
    "reason",
    "missing_artifacts",
    "blockers",
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
        "release_gate_result": None,
        "next_command": None,
        "reason": None,
        "missing_artifacts": [],
        "blockers": [],
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
    return state


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
            execution = verify.get("execution")
            if isinstance(execution, dict) and execution.get("status") == "FAIL":
                state["blockers"].append("gate5: execution phase failed")
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
