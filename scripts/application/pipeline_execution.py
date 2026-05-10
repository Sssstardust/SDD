#!/usr/bin/env python3
"""
Application-layer execution helpers extracted from run_pipeline.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable


def build_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    return env


def run_captured_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=build_subprocess_env(),
    )


def run_external_command(command: list[str], *, json_mode: bool = False, traced_runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None) -> int:
    if json_mode:
        if traced_runner is None:
            raise ValueError("traced_runner is required when json_mode=True")
        return traced_runner(command).returncode
    result = subprocess.run(command, check=False, env=build_subprocess_env())
    return result.returncode


def run_steps(
    steps: list[tuple[str, Callable[[], int]]],
    *,
    console_print: Callable[[str], None],
    on_step_completed: Callable[[str], None] | None = None,
) -> int:
    for label, step in steps:
        console_print(f"[RUN] {label}")
        code = step()
        if code == 0 and on_step_completed is not None:
            on_step_completed(label)
        if code != 0:
            console_print(f"[STOP] {label} failed with exit code {code}")
            return code
    return 0
