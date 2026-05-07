#!/usr/bin/env python3
"""
baseline_paths.py

根据附着目标项目解析当前激活的 baseline 目录。
"""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

from attached_project import DEFAULT_ATTACHMENT_PATH, load_attachment_config


ROOT = Path(__file__).resolve().parent.parent
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
    create: bool = False,
    migrate_legacy: bool = False,
) -> Path:
    effective_attachment_path = attachment_path if attachment_path.is_absolute() else (root / attachment_path).resolve()
    attachment = load_attachment_config(effective_attachment_path)
    if not isinstance(attachment, dict):
        baseline_dir = (root / ".spec" / "baseline").resolve()
        if create:
            baseline_dir.mkdir(parents=True, exist_ok=True)
        return baseline_dir

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
