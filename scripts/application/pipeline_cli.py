#!/usr/bin/env python3
"""
Application-layer CLI payload helpers for run_pipeline.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from attached_project import DEFAULT_ATTACHMENT_PATH
from infrastructure.project_artifact_paths import get_active_project_artifacts_dir
from infrastructure.versioning import detect_latest_design_path, reports_dir_for_design, resolve_feature_dir


def latest_report_artifact(feature_dir: str, filename: str) -> str | None:
    feature_dir_path = resolve_feature_dir(feature_dir)
    design_path = detect_latest_design_path(feature_dir_path)
    if not design_path.exists():
        return None
    report_path = reports_dir_for_design(feature_dir_path, design_path) / filename
    return str(report_path) if report_path.exists() else None


def collect_artifacts_for_command(args: argparse.Namespace) -> dict[str, object]:
    artifacts: dict[str, object] = {}
    cmd = getattr(args, "cmd", "")
    attachment_file = getattr(args, "attachment_file", None)
    profile = getattr(args, "profile", None)
    resolve_kwargs = {}
    if attachment_file:
        resolve_kwargs["attachment_path"] = Path(attachment_file)
    if profile:
        resolve_kwargs["profile"] = profile
    if cmd == "flow-status":
        flow_status_path = resolve_feature_dir(args.feature_dir, **resolve_kwargs) / "flow-status.json"
        project_state_path = resolve_feature_dir(args.feature_dir, **resolve_kwargs) / "project-state.json"
        if project_state_path.exists():
            artifacts["project_state_path"] = str(project_state_path)
        if flow_status_path.exists():
            artifacts["flow_status_path"] = str(flow_status_path)
    elif cmd == "generate-task-slices":
        task_slices_path = resolve_feature_dir(args.feature_dir, **resolve_kwargs) / "tasks" / "task-slices.generated.json"
        if task_slices_path.exists():
            artifacts["task_slices_path"] = str(task_slices_path)
    elif cmd == "gate5":
        verify_report_path = latest_report_artifact(args.feature_dir, "verify-report.json")
        if verify_report_path:
            artifacts["verify_report_path"] = verify_report_path
    elif cmd in {"release-gate", "pre-release-check", "go-live-check"}:
        release_gate_report_path = latest_report_artifact(args.feature_dir, "release-gate-report.json")
        if release_gate_report_path:
            artifacts["release_gate_report_path"] = release_gate_report_path
    elif cmd in {"project-next", "project-console-cycle", "project-cycle", "continue-project-flow"}:
        artifacts_dir = get_active_project_artifacts_dir(
            attachment_path=Path(attachment_file) if attachment_file else DEFAULT_ATTACHMENT_PATH,
            profile=profile,
            create=True,
        )
        project_next_path = artifacts_dir / "project-next.json"
        project_console_path = artifacts_dir / "project-console.json"
        if project_next_path.exists():
            artifacts["project_next_path"] = str(project_next_path)
        if project_console_path.exists():
            artifacts["project_console_path"] = str(project_console_path)
    return artifacts
