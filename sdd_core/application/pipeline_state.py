#!/usr/bin/env python3
"""
Thread-local execution state and basic subprocess runner for the SDD pipeline (FIX-016, FIX-019).
"""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from sdd_core.domain.pipeline import PipelineRunContext

ROOT = Path(__file__).resolve().parent.parent.parent
DOC_TEMPLATES = ROOT / "document" / "template"

_state = threading.local()


def _get_json_mode() -> bool:
    return getattr(_state, "json_mode", False)


def _get_execution_trace() -> list[dict[str, Any]]:
    if not hasattr(_state, "execution_trace"):
        _state.execution_trace = []
    return _state.execution_trace


def set_json_mode(enabled: bool) -> None:
    _state.json_mode = enabled


def reset_execution_trace() -> None:
    _get_execution_trace().clear()


def console_print(message: str) -> None:
    if not _get_json_mode():
        print(message)


def record_execution(
    command: list[str], result: subprocess.CompletedProcess[str]
) -> None:
    _get_execution_trace().append(
        {
            "command": command,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    )


def run_traced_captured_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    from sdd_core.application.pipeline_execution import run_captured_command
    result = run_captured_command(command)
    record_execution(command, result)
    return result


def run_external_command(command: list[str]) -> int:
    from sdd_core.application.pipeline_execution import run_external_command as app_run_external_command
    return app_run_external_command(
        command, json_mode=_get_json_mode(), traced_runner=run_traced_captured_command
    )


def _run_steps_compat(
    steps: list[tuple[str, Callable]], *, console_print_fn=console_print
) -> int:
    from sdd_core.application.pipeline_execution import run_steps
    return run_steps(steps, console_print=console_print_fn)


def build_pipeline_run_context(
    *,
    command: str,
    feature_dir: str | Path | None = None,
    strict: bool = False,
    attachment_file: str | Path | None = None,
    profile: str | None = None,
) -> PipelineRunContext:
    from sdd_core.infrastructure.versioning import resolve_feature_dir
    from sdd_core.domain.pipeline import PipelineRunContext
    normalized_feature_dir = (
        resolve_feature_dir(str(feature_dir)) if feature_dir else None
    )
    normalized_attachment = Path(attachment_file) if attachment_file else None
    return PipelineRunContext(
        command=command,
        feature_dir=normalized_feature_dir,
        strict=strict,
        attachment_file=normalized_attachment,
        profile=profile,
    )


def extract_issue_lines(raw_text: str, marker: str) -> list[str]:
    lines: list[str] = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if marker in stripped:
            lines.append(stripped)
    return lines


def collect_trace_warnings() -> list[str]:
    warnings: list[str] = []
    for entry in _get_execution_trace():
        warnings.extend(extract_issue_lines(str(entry.get("stdout") or ""), "[WARN]"))
        warnings.extend(extract_issue_lines(str(entry.get("stderr") or ""), "[WARN]"))
    return warnings


def collect_trace_errors(exit_code: int) -> list[str]:
    errors: list[str] = []
    for entry in _get_execution_trace():
        errors.extend(extract_issue_lines(str(entry.get("stdout") or ""), "[ERROR]"))
        errors.extend(extract_issue_lines(str(entry.get("stderr") or ""), "[ERROR]"))
    if exit_code != 0 and not errors:
        for entry in reversed(_get_execution_trace()):
            stderr_text = str(entry.get("stderr") or "").strip()
            stdout_text = str(entry.get("stdout") or "").strip()
            if stderr_text:
                errors.append(stderr_text.splitlines()[-1])
                break
            if stdout_text:
                errors.append(stdout_text.splitlines()[-1])
                break
    return errors
