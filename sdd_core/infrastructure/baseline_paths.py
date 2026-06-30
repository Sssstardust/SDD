#!/usr/bin/env python3
"""
Infrastructure helpers for resolving the active baseline directory.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

from ._root import ROOT
from sdd_core.domain.attached_project import DEFAULT_ATTACHMENT_PATH, load_attachment_config


def sanitize_bucket_name(value: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-._").lower()
    return sanitized or "attached-project"


def build_baseline_bucket_name(name: str, project_root: str) -> str:
    suffix = hashlib.sha256(project_root.encode("utf-8")).hexdigest()[:8]
    return f"{sanitize_bucket_name(name)}-{suffix}"


def migrate_legacy_baseline_dir(legacy_dir: Path, baseline_dir: Path) -> None:
    if not legacy_dir.exists():
        return
    for source in legacy_dir.rglob("*"):
        relative = source.relative_to(legacy_dir)
        target = baseline_dir / relative
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def get_active_spec_dir(
    *,
    root: Path = ROOT,
    attachment_path: Path = DEFAULT_ATTACHMENT_PATH,
    profile: str | None = None,
) -> Path:
    effective_attachment_path = attachment_path if attachment_path.is_absolute() else (root / attachment_path).resolve()
    attachment = load_attachment_config(effective_attachment_path, profile=profile)
    if isinstance(attachment, dict):
        project_root = attachment.get("project_root")
        if isinstance(project_root, str) and project_root.strip():
            p_root = Path(project_root.strip())
            return (p_root / ".spec").resolve()
    return (root / ".spec").resolve()


def get_active_baseline_dir(
    *,
    root: Path = ROOT,
    attachment_path: Path = DEFAULT_ATTACHMENT_PATH,
    profile: str | None = None,
    create: bool = False,
    migrate_legacy: bool = False,
) -> Path:
    spec_dir = get_active_spec_dir(root=root, attachment_path=attachment_path, profile=profile)
    effective_attachment_path = attachment_path if attachment_path.is_absolute() else (root / attachment_path).resolve()
    attachment = load_attachment_config(effective_attachment_path, profile=profile)
    from sdd_core.infrastructure.project_artifact_paths import get_active_project_artifacts_dir

    artifacts_dir = get_active_project_artifacts_dir(
        root=root,
        attachment_path=effective_attachment_path,
        profile=profile,
        create=create,
    )
    if not isinstance(attachment, dict):
        baseline_dir = (artifacts_dir / ".generated" / "baseline").resolve()
        if create:
            baseline_dir.mkdir(parents=True, exist_ok=True)
        if migrate_legacy:
            migrate_legacy_baseline_dir((spec_dir / "baseline").resolve(), baseline_dir)
        return baseline_dir

    explicit_project_id = attachment.get("project_id")
    if isinstance(explicit_project_id, str) and explicit_project_id.strip():
        bucket_name = explicit_project_id.strip()
    else:
        name = str(attachment.get("name") or "attached-project")
        project_root = str(attachment.get("project_root") or "")
        bucket_name = build_baseline_bucket_name(name, project_root)
    baseline_dir = (artifacts_dir / ".generated" / "baseline" / bucket_name).resolve()

    if create:
        baseline_dir.mkdir(parents=True, exist_ok=True)

    if migrate_legacy:
        legacy_dirs = [
            (spec_dir / "baselines" / bucket_name).resolve(),
            (spec_dir / "baseline").resolve(),
        ]
        for legacy_dir in legacy_dirs:
            migrate_legacy_baseline_dir(legacy_dir, baseline_dir)

    return baseline_dir
