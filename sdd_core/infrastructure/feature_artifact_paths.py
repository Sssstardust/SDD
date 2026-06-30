#!/usr/bin/env python3
"""Feature-level artifact path helpers."""

from __future__ import annotations

from pathlib import Path


def feature_generated_dir(feature_dir: Path, *, create: bool = False) -> Path:
    path = feature_dir / ".generated"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def project_state_path(feature_dir: Path, *, create_parent: bool = False) -> Path:
    return feature_generated_dir(feature_dir, create=create_parent) / "project-state.json"


def legacy_project_state_path(feature_dir: Path) -> Path:
    return feature_dir / "project-state.json"


def resolve_project_state_path(feature_dir: Path) -> Path:
    preferred = project_state_path(feature_dir)
    return preferred if preferred.exists() else legacy_project_state_path(feature_dir)


def task_slices_manifest_path(feature_dir: Path, *, create_parent: bool = False) -> Path:
    return feature_generated_dir(feature_dir, create=create_parent) / "task-slices.generated.json"


def legacy_task_slices_manifest_path(feature_dir: Path) -> Path:
    return feature_dir / "tasks" / "task-slices.generated.json"


def resolve_task_slices_manifest_path(feature_dir: Path) -> Path:
    preferred = task_slices_manifest_path(feature_dir)
    return preferred if preferred.exists() else legacy_task_slices_manifest_path(feature_dir)


def task_list_path(feature_dir: Path) -> Path:
    return feature_dir / "tasks" / "任务清单.md"
