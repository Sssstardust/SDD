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
    profile: str | None = None,
    create: bool = False,
) -> Path:
    effective_attachment_path = attachment_path if attachment_path.is_absolute() else (root / attachment_path).resolve()
    attachment = load_attachment_config(effective_attachment_path, profile=profile)
    if not isinstance(attachment, dict):
        target = (root / "specs").resolve()
        if create:
            target.mkdir(parents=True, exist_ok=True)
        return target

    explicit_project_id = attachment.get("project_id")
    if isinstance(explicit_project_id, str) and explicit_project_id.strip():
        bucket_name = explicit_project_id.strip()
    else:
        name = str(attachment.get("name") or "attached-project")
        project_root = str(attachment.get("project_root") or "")
        bucket_name = build_baseline_bucket_name(name, project_root)
    target = (root / ".spec" / "project-artifacts" / bucket_name).resolve()
    if create:
        target.mkdir(parents=True, exist_ok=True)
    return target


def describe_active_project_artifacts(
    *,
    root: Path = ROOT,
    attachment_path: Path = DEFAULT_ATTACHMENT_PATH,
    profile: str | None = None,
    create: bool = False,
) -> dict[str, object]:
    effective_attachment_path = attachment_path if attachment_path.is_absolute() else (root / attachment_path).resolve()
    attachment = load_attachment_config(effective_attachment_path, profile=profile)
    artifacts_dir = get_active_project_artifacts_dir(
        root=root,
        attachment_path=attachment_path,
        profile=profile,
        create=create,
    )

    if not isinstance(attachment, dict):
        return {
            "project_id": "local-specs",
            "project_name": "local-specs",
            "project_root": None,
            "artifacts_dir": str(artifacts_dir),
            "attachment_path": str(effective_attachment_path),
            "attachment_present": False,
        }

    project_root = str(attachment.get("project_root") or "") or None
    explicit_project_id = attachment.get("project_id")
    if isinstance(explicit_project_id, str) and explicit_project_id.strip():
        project_id = explicit_project_id.strip()
    else:
        name = str(attachment.get("name") or "attached-project")
        project_id = build_baseline_bucket_name(name, project_root or "")
    return {
        "project_id": project_id,
        "project_name": str(attachment.get("name") or "attached-project"),
        "project_root": project_root,
        "artifacts_dir": str(artifacts_dir),
        "attachment_path": str(effective_attachment_path),
        "attachment_present": True,
    }
