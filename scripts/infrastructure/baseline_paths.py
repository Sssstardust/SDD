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
from domain.attached_project import DEFAULT_ATTACHMENT_PATH, load_attachment_config


SPEC_DIR = ROOT / ".spec"
LEGACY_BASELINE_DIR = SPEC_DIR / "baseline"
BASELINE_BUCKETS_DIR = SPEC_DIR / "baselines"


def sanitize_bucket_name(value: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-._").lower()
    return sanitized or "attached-project"


def build_baseline_bucket_name(name: str, project_root: str) -> str:
    suffix = hashlib.sha1(project_root.encode("utf-8")).hexdigest()[:8]
    return f"{sanitize_bucket_name(name)}-{suffix}"


def get_active_baseline_dir(
    *,
    root: Path = ROOT,
    attachment_path: Path = DEFAULT_ATTACHMENT_PATH,
    profile: str | None = None,
    create: bool = False,
    migrate_legacy: bool = False,
) -> Path:
    effective_attachment_path = attachment_path if attachment_path.is_absolute() else (root / attachment_path).resolve()
    attachment = load_attachment_config(effective_attachment_path, profile=profile)
    if not isinstance(attachment, dict):
        baseline_dir = (root / ".spec" / "baseline").resolve()
        if create:
            baseline_dir.mkdir(parents=True, exist_ok=True)
        return baseline_dir

    explicit_project_id = attachment.get("project_id")
    if isinstance(explicit_project_id, str) and explicit_project_id.strip():
        bucket_name = explicit_project_id.strip()
    else:
        name = str(attachment.get("name") or "attached-project")
        project_root = str(attachment.get("project_root") or "")
        bucket_name = build_baseline_bucket_name(name, project_root)
    baseline_dir = (root / ".spec" / "baselines" / bucket_name).resolve()

    if create:
        baseline_dir.mkdir(parents=True, exist_ok=True)

    if migrate_legacy:
        legacy_dir = (root / ".spec" / "baseline").resolve()
        if legacy_dir.exists() and not any(baseline_dir.iterdir()):
            shutil.copytree(legacy_dir, baseline_dir, dirs_exist_ok=True)

    return baseline_dir
