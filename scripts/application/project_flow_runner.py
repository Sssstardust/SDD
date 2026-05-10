#!/usr/bin/env python3
"""
Helpers for project-level orchestration in run_pipeline.py.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from attached_project import DEFAULT_ATTACHMENT_PATH
from infrastructure.json_io import read_json
from infrastructure.project_artifact_paths import get_active_project_artifacts_dir


def project_next_json_path(
    *,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> Path:
    return (
        get_active_project_artifacts_dir(
            attachment_path=Path(attachment_file) if attachment_file else DEFAULT_ATTACHMENT_PATH,
            profile=profile,
            create=True,
        )
        / "project-next.json"
    )


def load_project_next_candidate(
    *,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> tuple[dict[str, object] | None, dict[str, object] | object]:
    path = project_next_json_path(attachment_file=attachment_file, profile=profile)
    payload = read_json(path) if path.exists() else {}
    candidate = payload.get("candidate") if isinstance(payload, dict) else None
    return candidate if isinstance(candidate, dict) else None, payload


def run_project_console_refresh_steps(
    *,
    refresh_project_state: Callable[..., int],
    build_flow_overview: Callable[..., int],
    build_project_next: Callable[..., int],
    build_tooling_hygiene: Callable[[], int],
    build_project_console: Callable[..., int],
    append_project_op: Callable[[str, dict[str, object]], None],
    console_print: Callable[[str], None],
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    steps = [
        (
            "refresh-project-state",
            lambda: refresh_project_state(
                attachment_file=attachment_file,
                profile=profile,
            ),
        ),
        (
            "flow-overview",
            lambda: build_flow_overview(
                attachment_file=attachment_file,
                profile=profile,
            ),
        ),
        (
            "project-next",
            lambda: build_project_next(
                attachment_file=attachment_file,
                profile=profile,
            ),
        ),
        ("tooling-hygiene", build_tooling_hygiene),
    ]
    for label, step in steps:
        console_print(f"[RUN] {label}")
        code = step()
        if code != 0:
            append_project_op("project-console-cycle", {"result": "fail", "failed_step": label})
            console_print(f"[STOP] {label} failed with exit code {code}")
            return code

    append_project_op("project-console-cycle", {"result": "ok"})
    console_print("[RUN] project-console")
    return build_project_console(attachment_file=attachment_file, profile=profile)


def capture_project_cycle_candidates(
    *,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> dict[str, object]:
    candidate, _payload = load_project_next_candidate(attachment_file=attachment_file, profile=profile)
    return {"candidate": candidate}


def dispatch_feature_next_command(
    *,
    next_command: str,
    feature_dir: str,
    strict: bool,
    init_feature: Callable[[str], int],
    bootstrap: Callable[[str], int],
    run_design_cycle: Callable[..., int],
    build_approval_summary: Callable[[str], int],
    run_approved_implementation_cycle: Callable[..., int],
    release_gate: Callable[[str, bool], int],
    run_full_flow: Callable[..., int],
    attachment_file: str | None = None,
    profile: str | None = None,
) -> tuple[str, Callable[[], int]] | None:
    if not next_command:
        return None
    if next_command.endswith(f"init-feature {Path(feature_dir).name}"):
        return ("init-feature", lambda: init_feature(Path(feature_dir).name))
    if "bootstrap" in next_command:
        return ("bootstrap", lambda: bootstrap(feature_dir))
    if "design-cycle" in next_command:
        return (
            "design-cycle",
            lambda: run_design_cycle(
                feature_dir,
                strict=strict,
                attachment_file=attachment_file,
                profile=profile,
            ),
        )
    if "build-approval-summary" in next_command:
        return ("build-approval-summary", lambda: build_approval_summary(feature_dir))
    if "approved-implementation-cycle" in next_command:
        return (
            "approved-implementation-cycle",
            lambda: run_approved_implementation_cycle(
                feature_dir,
                strict=strict,
                attachment_file=attachment_file,
                profile=profile,
            ),
        )
    if "release-gate" in next_command:
        return ("release-gate", lambda: release_gate(feature_dir, strict=strict))
    return (
        "full-flow",
        lambda: run_full_flow(
            feature_dir,
            strict=strict,
            attachment_file=attachment_file,
            profile=profile,
        ),
    )
