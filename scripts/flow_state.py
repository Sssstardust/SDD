#!/usr/bin/env python3
"""
flow_state.py

汇总 feature 当前所处的主流程状态，并给出下一步推荐命令。
"""

from __future__ import annotations

import re
from pathlib import Path

from json_io import read_json
from versioning import detect_latest_design_path, reports_dir_for_design


BOOTSTRAP_FILES = (
    "constitution.md",
    "architecture.md",
    "module-layout.md",
    "bootstrap-plan.md",
    "scaffold-report.json",
)


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


def inspect_feature_state(feature_dir: Path) -> dict[str, object]:
    state: dict[str, object] = {
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

    feature_brief = feature_dir / "feature-brief.md"
    if not feature_brief.exists():
        state["missing_artifacts"] = ["feature-brief.md"]
        state["current_stage"] = "uninitialized"
        state["next_command"] = f"python scripts/run_pipeline.py init-feature {feature_dir.name}"
        state["reason"] = "缺少 feature-brief.md"
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
            state["reason"] = "greenfield feature 缺少 bootstrap 产物"
            return state

    if not design_path.exists():
        state["missing_artifacts"] = ["design-v{N}.md"]
        state["current_stage"] = "feature-brief-ready"
        state["next_command"] = format_next_command("design-cycle", feature_dir, strict=strict_recommended)
        state["reason"] = "尚未生成 design-v{N}.md"
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
                    for warning in gate.get("warnings", []) if isinstance(gate.get("warnings"), list) else []:
                        state["blockers"].append(f"{gate_name}: {warning}")
                    for error in gate.get("errors", []) if isinstance(gate.get("errors"), list) else []:
                        state["blockers"].append(f"{gate_name}: {error}")
    else:
        state["missing_artifacts"].append(str(reports_dir / "gate-report.json"))

    approval_path = reports_dir / "approval.json"
    if approval_path.exists():
        approval = read_json(approval_path)
        if isinstance(approval, dict):
            state["approval_status"] = approval.get("status")
    elif state["risk_tier"] == "high":
        state["missing_artifacts"].append(str(reports_dir / "approval.json"))

    verify_path = reports_dir / "verify-report.json"
    verify_result = None
    if verify_path.exists():
        verify = read_json(verify_path)
        if isinstance(verify, dict):
            verify_result = verify.get("result")
            state["gate5_result"] = verify_result
            execution = verify.get("execution")
            if isinstance(execution, dict) and execution.get("status") == "FAIL":
                state["blockers"].append("gate5: 执行阶段失败")
    else:
        state["missing_artifacts"].append(str(reports_dir / "verify-report.json"))

    gate4_path = reports_dir / "gate4-skeleton.json"
    if not gate4_path.exists():
        state["missing_artifacts"].append(str(gate4_path))

    risk_high = state["risk_tier"] == "high"

    if state["gate2_result"] is None or state["gate3_result"] is None:
        state["current_stage"] = "design-in-progress"
        state["next_command"] = format_next_command("design-cycle", feature_dir, strict=strict_recommended)
        state["reason"] = "设计阶段门禁尚未全部完成"
        return state

    if risk_high and state["approval_status"] != "APPROVED":
        state["current_stage"] = "awaiting-approval"
        state["next_command"] = f"python scripts/run_pipeline.py build-approval-summary {feature_dir}"
        state["reason"] = "高风险设计尚未审批通过"
        return state

    if state["gate4_result"] == "FAIL" or state["gate5_result"] == "FAIL":
        state["current_stage"] = "implementation-needs-attention"
        state["next_command"] = format_next_command(
            "approved-implementation-cycle",
            feature_dir,
            strict=strict_recommended,
        )
        state["reason"] = "实现阶段门禁存在失败项，需要继续修复"
        return state

    if verify_result is None:
        state["current_stage"] = "approved-ready-for-implementation"
        state["next_command"] = format_next_command(
            "approved-implementation-cycle",
            feature_dir,
            strict=strict_recommended,
        )
        state["reason"] = "设计阶段已完成，尚未进入实现阶段门禁"
        return state

    if verify_result == "PASS" and state["release_gate_result"] != "PASS":
        state["current_stage"] = "verified-ready-for-release"
        state["next_command"] = format_next_command("release-gate", feature_dir, strict=strict_recommended)
        state["reason"] = "实现验证已通过，尚未完成上线前治理检查"
        return state

    if verify_result == "PASS":
        state["current_stage"] = "release-ready"
        state["next_command"] = format_next_command("release-gate", feature_dir, strict=strict_recommended)
        state["reason"] = "当前 feature 已完成实现验证与上线前治理检查"
        return state

    state["current_stage"] = "implementation-needs-attention"
    state["next_command"] = format_next_command("approved-implementation-cycle", feature_dir, strict=strict_recommended)
    state["reason"] = "实现阶段仍有未通过项，需要继续修复"
    return state
