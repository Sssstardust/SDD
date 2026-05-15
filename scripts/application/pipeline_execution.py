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


def run_steps_resilient(
    steps: list[tuple[str, Callable[[], int]]],
    *,
    console_print: Callable[[str], None],
    on_step_completed: Callable[[str], None] | None = None,
    diagnostic_steps: list[tuple[str, Callable[[], int]]] | None = None,
) -> int:
    """
    Run steps sequentially. If a step fails, attempt to run diagnostic steps before returning the error.
    """
    final_exit_code = 0
    for label, step in steps:
        console_print(f"[RUN] {label}")
        code = step()
        if code == 0:
            if on_step_completed is not None:
                on_step_completed(label)
        else:
            console_print(f"[ERROR] {label} failed with exit code {code}")
            final_exit_code = code
            break

    if final_exit_code != 0 and diagnostic_steps:
        console_print(f"[DIAGNOSE] Execution failed at step, running diagnostics...")
        for diag_label, diag_step in diagnostic_steps:
            console_print(f"[RUN DIAGNOSTIC] {diag_label}")
            diag_step()  # We ignore diagnostic step exit codes as they are best-effort
    
    return final_exit_code
