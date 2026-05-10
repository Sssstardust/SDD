#!/usr/bin/env python3
"""
Catalog of generator entrypoints during staged migration.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = ROOT / "scripts"

GENERATOR_ENTRYPOINTS: dict[str, str] = {
    "feature_brief": "generate_feature_brief.py",
    "task_slices": "generate_task_slices.py",
    "test_skeleton": "generate_test_skeleton.py",
    "approval_summary": "build_approval_summary.py",
}


def generator_entrypoint_path(name: str) -> Path:
    relative = GENERATOR_ENTRYPOINTS[name]
    return SCRIPTS_DIR / relative


def build_generator_command(name: str, *args: str, python_executable: str | None = None) -> list[str]:
    return [python_executable or sys.executable, str(generator_entrypoint_path(name)), *args]
