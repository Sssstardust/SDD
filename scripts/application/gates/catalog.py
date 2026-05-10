#!/usr/bin/env python3
"""
Catalog of gate entrypoints during staged migration.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = ROOT / "scripts"

GATE_ENTRYPOINTS: dict[str, str] = {
    "gate1": "gate1.py",
    "gate2": "check_design_truthfulness.py",
    "gate3": "check_arch_semantics.py",
    "gate4": "generate_test_skeleton.py",
    "gate5": "check_design_test_coverage.py",
    "release_gate": "release_gate.py",
}


def gate_entrypoint_path(name: str) -> Path:
    relative = GATE_ENTRYPOINTS[name]
    return SCRIPTS_DIR / relative


def build_gate_command(name: str, *args: str, python_executable: str | None = None) -> list[str]:
    return [python_executable or sys.executable, str(gate_entrypoint_path(name)), *args]
