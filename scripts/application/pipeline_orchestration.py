#!/usr/bin/env python3
"""
Shared orchestration helpers for run_pipeline flows.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from infrastructure.gate_cache import design_gate_input_hash, gate_report_path_for, implementation_gate_input_hash, should_skip_design_gate
from infrastructure.json_io import read_json


def _build_skippable_design_gate_step(
    gate_name: str,
    *,
    feature_dir: str,
    action: Callable[[], int],
) -> tuple[str, Callable[[], int]]:
    def _run() -> int:
        feature_path = Path(feature_dir).resolve()
        project_state_path = feature_path / "project-state.json"
        gate_cache: dict[str, dict[str, object]] = {}
        if project_state_path.exists():
            raw_state = read_json(project_state_path)
            if isinstance(raw_state, dict) and isinstance(raw_state.get("gate_cache"), dict):
                gate_cache = {
                    key: dict(value)
                    for key, value in raw_state.get("gate_cache", {}).items()
                    if isinstance(value, dict)
                }
        input_hash = design_gate_input_hash(feature_path, gate_name)
        if should_skip_design_gate(gate_cache, gate_name=gate_name, input_hash=input_hash):
            report_path = gate_report_path_for(feature_path, gate_name)
            if report_path.exists():
                return 0
        return action()

    return gate_name, _run


def _build_skippable_implementation_gate_step(
    gate_name: str,
    *,
    feature_dir: str,
    action: Callable[[], int],
) -> tuple[str, Callable[[], int]]:
    def _run() -> int:
        feature_path = Path(feature_dir).resolve()
        project_state_path = feature_path / "project-state.json"
        gate_cache: dict[str, dict[str, object]] = {}
        if project_state_path.exists():
            raw_state = read_json(project_state_path)
            if isinstance(raw_state, dict) and isinstance(raw_state.get("gate_cache"), dict):
                gate_cache = {
                    key: dict(value)
                    for key, value in raw_state.get("gate_cache", {}).items()
                    if isinstance(value, dict)
                }
        input_hash = implementation_gate_input_hash(feature_path, gate_name)
        if should_skip_design_gate(gate_cache, gate_name=gate_name, input_hash=input_hash):
            report_path = gate_report_path_for(feature_path, gate_name)
            if report_path.exists():
                return 0
        return action()

    return gate_name, _run


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
        _build_skippable_design_gate_step("gate1", feature_dir=feature_dir, action=lambda: gate1(feature_dir)),
        _build_skippable_design_gate_step("gate2", feature_dir=feature_dir, action=lambda: gate2(feature_dir, strict=strict)),
        _build_skippable_design_gate_step("gate3", feature_dir=feature_dir, action=lambda: gate3(feature_dir)),
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
        _build_skippable_implementation_gate_step("gate4", feature_dir=feature_dir, action=lambda: gate4(feature_dir)),
        _build_skippable_implementation_gate_step("gate5", feature_dir=feature_dir, action=lambda: gate5(feature_dir, require_attached_execution=strict, strict=strict)),
        ("update-design-index", lambda: update_design_index(feature_dir)),
        ("sync-baseline", lambda: sync_baseline(feature_dir)),
        ("validate-reports(implementation)", lambda: validate_reports(feature_dir, "implementation")),
    ]


def build_refresh_baseline_steps(
    *,
    refresh_module_map: Callable[..., int],
    refresh_schema_context: Callable[..., int],
    refresh_baseline_governance: Callable[[], int],
    check_baseline_keys: Callable[[str | None, str | None], int],
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
        ("check-baseline-keys", lambda: check_baseline_keys(attachment_file=attachment_file, profile=profile)),
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
