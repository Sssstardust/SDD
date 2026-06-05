#!/usr/bin/env python3
"""
Catalog of gate entrypoints during staged migration.
"""

from __future__ import annotations

import sys
from pathlib import Path


GATE_COMMANDS: dict[str, str] = {
    "gate1": "gate1",
    "gate2": "gate2",
    "gate3": "gate3",
    "gate4": "gate4",
    "gate5": "gate5",
    "release_gate": "release-gate",
}

GATE_ENTRYPOINTS = GATE_COMMANDS


def gate_entrypoint_path(name: str) -> Path:
    return Path("sdd_core") / "run_pipeline.py"


def build_gate_command(name: str, *args: str, python_executable: str | None = None) -> list[str]:
    return [
        python_executable or sys.executable,
        "-m",
        "sdd_core.run_pipeline",
        GATE_COMMANDS[name],
        *args,
    ]
