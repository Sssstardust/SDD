#!/usr/bin/env python3
"""
project_artifact_paths.py

根据附着目标项目解析项目级控制台与状态产物输出目录。
"""

from __future__ import annotations

from pathlib import Path

from attached_project import DEFAULT_ATTACHMENT_PATH, load_attachment_config
from baseline_paths import build_baseline_bucket_name


ROOT = Path(__file__).resolve().parent.parent
LEGACY_PROJECT_ARTIFACTS_DIR = ROOT / "specs"
PROJECT_ARTIFACT_BUCKETS_DIR = ROOT / ".spec" / "project-artifacts"


def get_active_project_artifacts_dir(
    *,
    root: Path = ROOT,
    attachment_path: Path = DEFAULT_ATTACHMENT_PATH,
    create: bool = False,
) -> Path:
    effective_attachment_path = attachment_path if attachment_path.is_absolute() else (root / attachment_path).resolve()
    attachment = load_attachment_config(effective_attachment_path)
    if not isinstance(attachment, dict):
        target = (root / "specs").resolve()
        if create:
            target.mkdir(parents=True, exist_ok=True)
        return target

    name = str(attachment.get("name") or "attached-project")
    project_root = str(attachment.get("project_root") or "")
    bucket_name = build_baseline_bucket_name(name, project_root)
    target = (root / ".spec" / "project-artifacts" / bucket_name).resolve()
    if create:
        target.mkdir(parents=True, exist_ok=True)
    return target
