#!/usr/bin/env python3
"""
Catalog of refresher entrypoints during staged migration.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = ROOT / "scripts"

REFRESHER_ENTRYPOINTS: dict[str, str] = {
    "module_map": "refresh_module_map.py",
    "schema_context": "refresh_schema_context.py",
    "project_state": "refresh_project_state.py",
    "baseline_governance": "refresh_baseline_governance.py",
}


def refresher_entrypoint_path(name: str) -> Path:
    relative = REFRESHER_ENTRYPOINTS[name]
    return SCRIPTS_DIR / relative


def build_refresher_command(name: str, *args: str, python_executable: str | None = None) -> list[str]:
    return [python_executable or sys.executable, str(refresher_entrypoint_path(name)), *args]
