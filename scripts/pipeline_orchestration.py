#!/usr/bin/env python3
"""
Shared orchestration helpers for run_pipeline flows.
"""

from __future__ import annotations

from collections.abc import Callable


def append_post_flow_steps(
    steps: list[tuple[str, Callable[[], int]]],
    *,
    feature_dir: str,
    refresh_feature_state: Callable[..., int],
    run_project_console_cycle: Callable[..., int],
    attachment_file: str | None = None,
    profile: str | None = None,
) -> list[tuple[str, Callable[[], int]]]:
    return [
        *steps,
        (
            "flow-status",
            lambda: refresh_feature_state(
                feature_dir,
                attachment_file=attachment_file,
                profile=profile,
            ),
        ),
        (
            "project-console-cycle",
            lambda: run_project_console_cycle(
                attachment_file=attachment_file,
                profile=profile,
            ),
        ),
    ]


def build_design_gate_steps(
    *,
    feature_dir: str,
    strict: bool,
    run_refresh_baseline: Callable[..., int],
    gate1: Callable[[str], int],
    gate2: Callable[[str, bool], int],
    gate3: Callable[[str], int],
    check_approval: Callable[[str], int],
    update_design_index: Callable[[str], int],
    generate_task_slices: Callable[[str], int],
    validate_reports: Callable[[str, str], int],
    build_approval_summary: Callable[[str], int],
    attachment_file: str | None = None,
    profile: str | None = None,
) -> list[tuple[str, Callable[[], int]]]:
    return [
        (
            "refresh-baseline",
            lambda: run_refresh_baseline(
                strict=strict,
                feature_dir=feature_dir,
                attachment_file=attachment_file,
                profile=profile,
            ),
        ),
        ("gate1", lambda: gate1(feature_dir)),
        ("gate2", lambda: gate2(feature_dir, strict=strict)),
        ("gate3", lambda: gate3(feature_dir)),
        ("check-approval", lambda: check_approval(feature_dir)),
        ("update-design-index", lambda: update_design_index(feature_dir)),
        ("generate-task-slices", lambda: generate_task_slices(feature_dir)),
        ("validate-reports(design)", lambda: validate_reports(feature_dir, "design")),
        ("build-approval-summary", lambda: build_approval_summary(feature_dir)),
    ]


def build_implementation_gate_steps(
    *,
    feature_dir: str,
    strict: bool,
    gate4: Callable[[str], int],
    gate5: Callable[[str, bool, bool], int],
    update_design_index: Callable[[str], int],
    sync_baseline: Callable[[str], int],
    validate_reports: Callable[[str, str], int],
) -> list[tuple[str, Callable[[], int]]]:
    return [
        ("gate4", lambda: gate4(feature_dir)),
        ("gate5", lambda: gate5(feature_dir, require_attached_execution=strict, strict=strict)),
        ("update-design-index", lambda: update_design_index(feature_dir)),
        ("sync-baseline", lambda: sync_baseline(feature_dir)),
        ("validate-reports(implementation)", lambda: validate_reports(feature_dir, "implementation")),
    ]


def build_refresh_baseline_steps(
    *,
    refresh_module_map: Callable[..., int],
    refresh_schema_context: Callable[..., int],
    refresh_baseline_governance: Callable[[], int],
    attachment_file: str | None = None,
    profile: str | None = None,
    refresh_strategy: dict[str, object] | None = None,
) -> list[tuple[str, Callable[[], int]]]:
    strategy = refresh_strategy or {}
    return [
        (
            "refresh-module-map",
            lambda: refresh_module_map(
                attachment_file=attachment_file,
                profile=profile,
            ),
        ),
        (
            "refresh-schema-context",
            lambda: refresh_schema_context(
                attachment_file=attachment_file,
                profile=profile,
                **strategy,
            ),
        ),
        ("refresh-baseline-governance", refresh_baseline_governance),
    ]


def build_feature_cycle_steps(
    *,
    feature_dir: str,
    continue_action: Callable[[], int],
    refresh_feature_state: Callable[..., int],
) -> list[tuple[str, Callable[[], int]]]:
    return [
        ("flow-status(before)", lambda: refresh_feature_state(feature_dir)),
        ("continue-flow", continue_action),
        ("flow-status(after)", lambda: refresh_feature_state(feature_dir)),
    ]
