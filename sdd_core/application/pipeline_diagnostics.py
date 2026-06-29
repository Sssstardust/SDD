#!/usr/bin/env python3
"""
Diagnostic and repair helpers for features (FIX-016).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sdd_core.application.pipeline_state import console_print


def feature_repair_report(
    feature_dir: str,
    *,
    apply_fixes: bool = False,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    from sdd_core.domain.attached_project import DEFAULT_ATTACHMENT_PATH
    from sdd_core.infrastructure.versioning import resolve_feature_dir, detect_latest_design_path, reports_dir_for_design
    from sdd_core.application.preflight import missing_feature_prerequisites
    from sdd_core.infrastructure.baseline_paths import get_active_baseline_dir
    from sdd_core.application.gates.gate_runtime import detect_context_missing
    from sdd_core.application.pipeline_commands import init_approval, generate_task_slices

    attachment_path = (
        Path(attachment_file) if attachment_file else DEFAULT_ATTACHMENT_PATH
    )
    feature_path = Path(
        resolve_feature_dir(
            feature_dir, attachment_path=attachment_path, profile=profile
        )
    )
    missing = missing_feature_prerequisites(
        feature_path,
        require_feature_brief=True,
        require_design=True,
        require_approval=False,
        require_task_slices_manifest=False,
        require_task_slice_files=False,
    )
    actions_attempted: list[str] = []
    warnings: list[str] = []

    if not feature_path.exists():
        missing.append(f"missing feature directory: {feature_path}")

    feature_brief = feature_path / "需求规格.md"
    design_path = detect_latest_design_path(feature_path)
    reports_dir = (
        reports_dir_for_design(feature_path, design_path)
        if design_path
        else feature_path / "reports" / "v1"
    )
    approval_path = reports_dir / "approval.json"
    task_slices_manifest = feature_path / "tasks" / "task-slices.generated.json"
    context_check = None
    baseline_dir = get_active_baseline_dir(
        attachment_path=attachment_path,
        profile=profile,
        create=True,
        migrate_legacy=True,
    )
    design_pack_dir = resolve_feature_dir(
        feature_dir, attachment_path=attachment_path, profile=profile
    )
    context_check = detect_context_missing(
        feature_path, design_pack_dir / "design-pack", baseline_dir
    )

    if apply_fixes and feature_brief.exists() and design_path.exists():
        if not approval_path.exists():
            code = init_approval(str(feature_path))
            actions_attempted.append("init-approval")
            if code != 0:
                warnings.append("init-approval failed")
        if not task_slices_manifest.exists():
            code = generate_task_slices(str(feature_path))
            actions_attempted.append("generate-task-slices")
            if code != 0:
                warnings.append("generate-task-slices failed")

    remaining = missing_feature_prerequisites(
        feature_path,
        require_feature_brief=True,
        require_design=True,
        require_approval=False,
        require_task_slices_manifest=False,
        require_task_slice_files=False,
    )

    if not approval_path.exists() and feature_brief.exists():
        warnings.append(f"missing approval scaffold: {approval_path}")
    if (
        not task_slices_manifest.exists()
        and feature_brief.exists()
        and design_path.exists()
    ):
        warnings.append(f"missing task slices manifest: {task_slices_manifest}")
    if (
        isinstance(context_check, dict)
        and context_check.get("status") == "CONTEXT_MISSING"
    ):
        for item in context_check.get("missing", []):  # type: ignore
            warnings.append(f"context missing: {item}")

    status = "ok" if not remaining and not warnings else "warn"
    return {
        "status": status,
        "feature_dir": str(feature_path),
        "missing": remaining,
        "warnings": warnings,
        "actions_attempted": actions_attempted,
        "approval_path": str(approval_path),
        "task_slices_manifest": str(task_slices_manifest),
        "context_check": context_check,
    }


def feature_doctor_command(
    feature_dir: str,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    payload = feature_repair_report(
        feature_dir, apply_fixes=False, attachment_file=attachment_file, profile=profile
    )
    console_print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "ok" else 1


def feature_repair_command(
    feature_dir: str,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    payload = feature_repair_report(
        feature_dir, apply_fixes=True, attachment_file=attachment_file, profile=profile
    )
    console_print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "ok" else 1
