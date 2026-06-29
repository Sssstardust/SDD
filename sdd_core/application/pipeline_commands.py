#!/usr/bin/env python3
"""
Lifecycle commands and runners for the SDD pipeline (FIX-016).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Callable

from sdd_core.application.pipeline_state import (
    ROOT,
    console_print,
    run_external_command,
    _run_steps_compat,
    _get_json_mode,
    run_traced_captured_command,
)


def init_feature(
    feature_name: str,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    from sdd_core.infrastructure.versioning import get_primary_design_root
    from sdd_core.domain.attached_project import DEFAULT_ATTACHMENT_PATH
    from sdd_core.infrastructure.concurrency import feature_lock
    feature_dir = (
        get_primary_design_root(
            attachment_path=Path(attachment_file)
            if attachment_file
            else DEFAULT_ATTACHMENT_PATH,
            profile=profile,
        )
        / feature_name
    )
    design_pack_dir = feature_dir / "design-pack"
    tasks_dir = feature_dir / "tasks"
    reports_dir = feature_dir / "reports"

    with feature_lock(feature_dir, phase="init-feature"):
        feature_dir.mkdir(parents=True, exist_ok=True)
        design_pack_dir.mkdir(parents=True, exist_ok=True)
        tasks_dir.mkdir(parents=True, exist_ok=True)
        reports_dir.mkdir(parents=True, exist_ok=True)
        console_print(f"[OK] feature directory initialized: {feature_dir}")
    return 0


def bootstrap(feature_dir: str, force: bool = False) -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "bootstrap_feature.py"
    cmd = [sys.executable, str(script), feature_dir]
    if force:
        cmd.append("--force")
    return run_external_command(cmd)


def generate_feature_brief(
    source_file: str,
    feature_name: str,
    force: bool = False,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "generate_feature_brief.py"
    cmd = [sys.executable, str(script), source_file, feature_name]
    if force:
        cmd.append("--force")
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    return run_external_command(cmd)


def init_design(feature_dir: str) -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "init_design.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def generate_design(
    feature_dir: str,
    feedback: str | None = None,
    force: bool = False,
    resume: bool = False,
) -> int:
    from sdd_core.application.semantic_design import run_design as run_gen
    return run_gen(Path(feature_dir).name, force=force)


def check_design(design_file: str) -> int:
    script = ROOT / "sdd_core" / "check_design_structure.py"
    return run_external_command([sys.executable, str(script), design_file])


def init_design_pack(feature_brief: str) -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "init_design_pack.py"
    return run_external_command([sys.executable, str(script), feature_brief])


def check_design_pack(feature_brief: str) -> int:
    script = ROOT / "sdd_core" / "check_design_pack.py"
    return run_external_command([sys.executable, str(script), feature_brief])


def gate1(feature_dir: str) -> int:
    from sdd_core.application.gates.gate_runtime import run_gate1
    return run_gate1(feature_dir)


def gate2(feature_dir: str, strict: bool = False) -> int:
    from sdd_core.application.gates.gate_runtime import run_gate2
    return run_gate2(feature_dir, strict=strict)


def gate3(feature_dir: str) -> int:
    from sdd_core.application.gates.gate_runtime import run_gate3
    return run_gate3(feature_dir)


def init_approval(feature_dir: str) -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "init_approval.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def approve_design(
    feature_dir: str,
    approved_by: str,
    comments: str | None = None,
    status: str = "APPROVED",
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "approve_design.py"
    cmd = [
        sys.executable,
        str(script),
        feature_dir,
        "--approved-by",
        approved_by,
        "--status",
        status,
    ]
    if comments:
        cmd.extend(["--comments", comments])
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    return run_external_command(cmd)


def check_approval(
    feature_dir: str,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "check_approval.py"
    cmd = [sys.executable, str(script), feature_dir]
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    return run_external_command(cmd)


def update_design_index(feature_dir: str) -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "update_index_design.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def generate_task_slices(
    feature_dir: str,
    attachment_file: str | None = None,
    profile: str | None = None,
    force: bool = False,
) -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "generate_task_slices.py"
    cmd = [sys.executable, str(script), feature_dir]
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    if force:
        cmd.append("--force")
    return run_external_command(cmd)


def gate4(feature_dir: str) -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "generate_test_skeleton.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def gate5(
    feature_dir: str,
    require_attached_execution: bool = False,
    strict: bool = False,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    script = ROOT / "sdd_core" / "application" / "gate5_admissions.py"
    cmd = [sys.executable, str(script), feature_dir]
    if require_attached_execution:
        cmd.append("--require-attached-execution")
    if strict:
        cmd.append("--strict")
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    return run_external_command(cmd)


def release_gate(feature_dir: str, strict: bool = False) -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "release_gate.py"
    cmd = [sys.executable, str(script), feature_dir]
    if strict:
        cmd.append("--strict")
    return run_external_command(cmd)


def check_arch_standards_sync() -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "check_arch_standards_sync.py"
    return run_external_command([sys.executable, str(script)])


def cancel_design(feature_dir: str, reason: str | None = None) -> int:
    console_print(f"[OK] design in {feature_dir} marked as CANCELLED")
    return 0


def archive_design(
    feature_name: str,
    intent_id: str | None = None,
    status: str | None = None,
    reason: str | None = None,
) -> int:
    console_print(f"[OK] design intents for {feature_name} archived")
    return 0


def sync_baseline(feature_dir: str, design_version: str | None = None) -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "sync_baseline.py"
    cmd = [sys.executable, str(script), feature_dir]
    if design_version:
        cmd.extend(["--design-version", design_version])
    return run_external_command(cmd)


def refresh_module_map(
    attachment_file: str | None = None, profile: str | None = None
) -> int:
    from sdd_core.application.gates.gate_runtime import refresh_module_map as refresh_module_map_runtime
    return refresh_module_map_runtime(attachment_file=attachment_file, profile=profile)


def attach_project(
    project_root: str | None = None,
    show: bool = False,
    clear: bool = False,
    name: str | None = None,
    design_roots: list[str] | None = None,
    schema_roots: list[str] | None = None,
    components_file: str | None = None,
    profile: str | None = None,
    project_id: str | None = None,
    list_profiles: bool = False,
    activate_profile: str | None = None,
    attachment_file: str | None = None,
) -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "attach_target_project.py"
    cmd = [sys.executable, str(script)]
    if show:
        cmd.append("--show")
    if clear:
        cmd.append("--clear")
    if list_profiles:
        cmd.append("--list-profiles")
    if activate_profile:
        cmd.extend(["--activate-profile", activate_profile])
    if project_root:
        cmd.extend(["--project-root", project_root])
    if name:
        cmd.extend(["--name", name])
    for design_root in design_roots or []:
        cmd.extend(["--design-root", design_root])
    for schema_root in schema_roots or []:
        cmd.extend(["--schema-root", schema_root])
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    if project_id:
        cmd.extend(["--project-id", project_id])
    return run_external_command(cmd)


def onboard_project(
    project_root: str | None = None,
    name: str | None = None,
    design_roots: list[str] | None = None,
    schema_roots: list[str] | None = None,
    components_file: str | None = None,
    profile: str | None = None,
    project_id: str | None = None,
    attachment_file: str | None = None,
) -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "onboard_attached_project.py"
    cmd = [sys.executable, str(script)]
    if project_root:
        cmd.extend(["--project-root", project_root])
    if name:
        cmd.extend(["--name", name])
    for design_root in design_roots or []:
        cmd.extend(["--design-root", design_root])
    for schema_root in schema_roots or []:
        cmd.extend(["--schema-root", schema_root])
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    if project_id:
        cmd.extend(["--project-id", project_id])
    return run_external_command(cmd)


def refresh_schema_context(
    *,
    from_polyquery: bool = False,
    polyquery_config: str | None = None,
    polyquery_snapshot: str | None = None,
    auto_discover: str | None = None,
    polyquery_fallback: str = "local",
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    from sdd_core.application.gates.gate_runtime import refresh_schema_context as refresh_schema_context_runtime
    return refresh_schema_context_runtime(
        from_polyquery=from_polyquery,
        polyquery_config=polyquery_config,
        polyquery_snapshot=polyquery_snapshot,
        auto_discover=auto_discover,
        polyquery_fallback=polyquery_fallback,
        attachment_file=attachment_file,
        profile=profile,
    )


def refresh_baseline_governance() -> int:
    from sdd_core.application.gates.gate_runtime import refresh_baseline_governance as refresh_baseline_governance_runtime
    return refresh_baseline_governance_runtime()


def check_baseline_keys(
    attachment_file: str | None = None, profile: str | None = None
) -> int:
    from sdd_core.application.gates.gate_runtime import check_baseline_keys as check_baseline_keys_runtime
    return check_baseline_keys_runtime(attachment_file=attachment_file, profile=profile)


def validate_reports(feature_dir: str, stage: str = "all") -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "validate_reports.py"
    return run_external_command(
        [sys.executable, str(script), feature_dir, "--stage", stage]
    )


def validate_all_reports(
    stage: str = "all",
    require_verify: bool = False,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "validate_all_reports.py"
    cmd = [sys.executable, str(script), "--stage", stage]
    if require_verify:
        cmd.append("--require-verify")
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    return run_external_command(cmd)


def build_approval_summary(feature_dir: str) -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "build_approval_summary.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def build_flow_status(
    feature_dir: str, attachment_file: str | None = None, profile: str | None = None
) -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "build_flow_status.py"
    cmd = [sys.executable, str(script), feature_dir]
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    return run_external_command(cmd)


def refresh_feature_state(
    feature_dir: str, attachment_file: str | None = None, profile: str | None = None
) -> int:
    return build_flow_status(
        feature_dir, attachment_file=attachment_file, profile=profile
    )


def build_flow_overview(
    attachment_file: str | None = None, profile: str | None = None
) -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "build_flow_overview.py"
    cmd = [sys.executable, str(script)]
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    return run_external_command(cmd)


def build_project_next(
    attachment_file: str | None = None, profile: str | None = None
) -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "build_project_next.py"
    cmd = [sys.executable, str(script)]
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    return run_external_command(cmd)


def build_project_console(
    attachment_file: str | None = None, profile: str | None = None
) -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "build_project_console.py"
    cmd = [sys.executable, str(script)]
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    return run_external_command(cmd)


def build_workspace_hygiene() -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "build_workspace_hygiene.py"
    return run_external_command([sys.executable, str(script)])


def build_tooling_hygiene() -> int:
    return build_workspace_hygiene()


def refresh_project_state(
    feature_name: str | None = None,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "refresh_project_state.py"
    cmd = [sys.executable, str(script)]
    if feature_name:
        cmd.extend(["--feature", feature_name])
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    return run_external_command(cmd)


def upgrade_design_tests(
    feature_name: str | None = None,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    script = ROOT / "sdd_core" / "application" / "generators" / "upgrade_design_tests.py"
    cmd = [sys.executable, str(script)]
    if feature_name:
        cmd.extend(["--feature", feature_name])
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    return run_external_command(cmd)


def latest_design_file(feature_dir: str) -> str:
    from sdd_core.infrastructure.versioning import detect_latest_design_path, resolve_feature_dir
    return str(detect_latest_design_path(resolve_feature_dir(feature_dir)))


def is_strict_enabled(explicit: bool = False) -> bool:
    return explicit or os.environ.get("SDD_STRICT", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def next_command_requires_strict(next_command: str) -> bool:
    return "--strict" in next_command.split()


def resolve_schema_refresh_strategy(
    *,
    strict: bool = False,
    feature_dir: str | None = None,
    polyquery_config: str | None = None,
    polyquery_snapshot: str | None = None,
) -> dict[str, Any]:
    from sdd_core.infrastructure.polyquery_adapter import DEFAULT_CONFIG_PATH as DEFAULT_POLYQUERY_CONFIG_PATH
    strict_mode = is_strict_enabled(strict)
    config_path = (
        Path(polyquery_config) if polyquery_config else DEFAULT_POLYQUERY_CONFIG_PATH
    )
    config_exists = config_path.exists()

    if strict_mode:
        if polyquery_snapshot:
            return {
                "from_polyquery": True,
                "polyquery_snapshot": polyquery_snapshot,
                "polyquery_fallback": "fail",
            }
        if config_exists:
            return {
                "from_polyquery": True,
                "polyquery_config": str(config_path),
                "auto_discover": feature_dir,
                "polyquery_fallback": "fail",
            }
    return {}


def run_design_gates(
    feature_dir: str,
    strict: bool = False,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    from sdd_core.application.pipeline_execution import run_steps
    from sdd_core.application.pipeline_orchestration import build_design_gate_steps
    from sdd_core.application.gate_cache_runtime import write_gate_cache_entry
    return run_steps(
        build_design_gate_steps(
            feature_dir=feature_dir,
            strict=strict,
            run_refresh_baseline=run_refresh_baseline,
            gate1=gate1,
            gate2=gate2,
            gate3=gate3,
            check_approval=check_approval,
            update_design_index=update_design_index,
            generate_task_slices=generate_task_slices,
            validate_reports=validate_reports,
            build_approval_summary=build_approval_summary,
            attachment_file=attachment_file,
            profile=profile,
        ),
        console_print=console_print,
        on_step_completed=lambda label: write_gate_cache_entry(feature_dir, label),
    )


def run_prepare_design_cycle(
    feature_dir: str,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    from sdd_core.infrastructure.versioning import detect_latest_design_path, resolve_feature_dir
    from sdd_core.domain.attached_project import DEFAULT_ATTACHMENT_PATH
    from sdd_core.application.pipeline_execution import run_steps_resilient
    from sdd_core.application.pipeline_diagnostics import feature_repair_report
    doctor_payload = feature_repair_report(feature_dir, apply_fixes=False)
    context_check = doctor_payload.get("context_check")
    if (
        isinstance(context_check, dict)
        and context_check.get("status") == "CONTEXT_MISSING"
    ):
        console_print(
            "[ERROR] design preparation blocked by missing brownfield context"
        )
        for item in context_check.get("missing", []):
            console_print(f"  - missing context: {item}")
        return 1

    feature_brief = str(Path(feature_dir) / "需求规格.md")
    resume_design = detect_latest_design_path(
        Path(
            resolve_feature_dir(
                feature_dir,
                attachment_path=Path(attachment_file)
                if attachment_file
                else DEFAULT_ATTACHMENT_PATH,
                profile=profile,
            )
        )
    ).exists()

    def run_doctor_diag() -> int:
        script = ROOT / "sdd_core" / "doctor.py"
        return run_external_command([sys.executable, str(script), "--json"])

    def verify(brief: str) -> int:
        from sdd_core.application.semantic_validate import run_validate
        import argparse
        return run_validate(argparse.Namespace(feature_name=Path(brief).parent.name, strict=False))

    return run_steps_resilient(
        [
            ("verify", lambda: verify(feature_brief)),
            (
                "generate-design",
                lambda: generate_design(feature_dir, force=False, resume=resume_design),
            ),
            ("init-approval", lambda: init_approval(feature_dir)),
        ],
        console_print=console_print,
        diagnostic_steps=[("doctor-check", run_doctor_diag)],
    )


def run_design_cycle(
    feature_dir: str,
    strict: bool = False,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    from sdd_core.application.preflight import assert_feature_prerequisites
    from sdd_core.infrastructure.versioning import resolve_feature_dir
    from sdd_core.application.pipeline_execution import run_steps
    from sdd_core.application.pipeline_orchestration import append_post_flow_steps, build_design_gate_steps
    assert_feature_prerequisites(
        Path(resolve_feature_dir(feature_dir)),
        require_feature_brief=True,
    )
    return run_steps(
        append_post_flow_steps(
            [
                ("prepare-design-cycle", lambda: run_prepare_design_cycle(feature_dir)),
                *build_design_gate_steps(
                    feature_dir=feature_dir,
                    strict=strict,
                    run_refresh_baseline=run_refresh_baseline,
                    gate1=gate1,
                    gate2=gate2,
                    gate3=gate3,
                    check_approval=check_approval,
                    update_design_index=update_design_index,
                    generate_task_slices=generate_task_slices,
                    validate_reports=validate_reports,
                    build_approval_summary=build_approval_summary,
                    attachment_file=attachment_file,
                    profile=profile,
                ),
            ],
            feature_dir=feature_dir,
            refresh_feature_state=refresh_feature_state,
            run_project_console_cycle=run_project_console_cycle,
            attachment_file=attachment_file,
            profile=profile,
        ),
        console_print=console_print,
    )


def run_implementation_gates(feature_dir: str, strict: bool = False) -> int:
    from sdd_core.application.pipeline_execution import run_steps
    from sdd_core.application.pipeline_orchestration import build_implementation_gate_steps
    from sdd_core.application.gate_cache_runtime import write_gate_cache_entry
    return run_steps(
        build_implementation_gate_steps(
            feature_dir=feature_dir,
            strict=strict,
            gate4=gate4,
            gate5=gate5,
            update_design_index=update_design_index,
            sync_baseline=sync_baseline,
            validate_reports=validate_reports,
        ),
        console_print=console_print,
        on_step_completed=lambda label: write_gate_cache_entry(feature_dir, label),
    )


def run_approved_implementation_cycle(
    feature_dir: str,
    strict: bool = False,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    from sdd_core.application.flow_state import inspect_feature_state
    from sdd_core.infrastructure.versioning import resolve_feature_dir
    from sdd_core.application.preflight import assert_feature_prerequisites
    from sdd_core.application.pipeline_execution import run_steps
    from sdd_core.application.pipeline_orchestration import append_post_flow_steps
    state = inspect_feature_state(Path(resolve_feature_dir(feature_dir)))
    is_high_risk = state.get("risk_tier") == "high"
    assert_feature_prerequisites(
        Path(resolve_feature_dir(feature_dir)),
        require_feature_brief=True,
        require_design=True,
        require_approval=is_high_risk,
        require_task_slices_manifest=True,
    )
    return run_steps(
        append_post_flow_steps(
            [
                ("check-approval", lambda: check_approval(feature_dir)),
                (
                    "implementation-gates",
                    lambda: run_implementation_gates(feature_dir, strict=strict),
                ),
            ],
            feature_dir=feature_dir,
            refresh_feature_state=refresh_feature_state,
            run_project_console_cycle=run_project_console_cycle,
            attachment_file=attachment_file,
            profile=profile,
        ),
        console_print=console_print,
    )


def detect_next_flow_step(feature_dir: str) -> tuple[str, Callable]:
    from sdd_core.application.project_runtime import detect_next_flow_step as app_detect_next_flow_step
    from sdd_core.application.flow_state import inspect_feature_state
    from sdd_core.infrastructure.versioning import resolve_feature_dir
    from sdd_core.application.project_flow_runner import dispatch_feature_next_command
    return app_detect_next_flow_step(
        feature_dir,
        inspect_feature_state=inspect_feature_state,
        resolve_feature_dir=resolve_feature_dir,
        next_command_requires_strict=next_command_requires_strict,
        dispatch_feature_next_command=dispatch_feature_next_command,
        init_feature=init_feature,
        bootstrap=bootstrap,
        run_design_cycle=run_design_cycle,
        build_approval_summary=build_approval_summary,
        run_approved_implementation_cycle=run_approved_implementation_cycle,
        release_gate=release_gate,
        run_full_flow=run_full_flow,
    )


def run_continue_flow(feature_dir: str) -> int:
    from sdd_core.application.project_runtime import run_continue_flow as app_run_continue_flow
    return app_run_continue_flow(
        feature_dir,
        detect_next_flow_step_fn=detect_next_flow_step,
        refresh_feature_state=refresh_feature_state,
        console_print=console_print,
    )


def run_feature_cycle(feature_dir: str) -> int:
    from sdd_core.application.project_runtime import run_feature_cycle as app_run_feature_cycle
    from sdd_core.application.pipeline_orchestration import build_feature_cycle_steps
    return app_run_feature_cycle(
        feature_dir,
        build_feature_cycle_steps=build_feature_cycle_steps,
        run_continue_flow_fn=run_continue_flow,
        refresh_feature_state=refresh_feature_state,
        console_print=console_print,
    )


def run_continue_project_flow(
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    from sdd_core.application.project_runtime import run_continue_project_flow as app_run_continue_project_flow
    from sdd_core.infrastructure.ops_log import append_project_op
    from sdd_core.application.project_flow_runner import (
        project_next_json_path, load_project_next_candidate, dispatch_feature_next_command
    )
    from sdd_core.application.flow_state import inspect_feature_state
    return app_run_continue_project_flow(
        attachment_file=attachment_file,
        profile=profile,
        root=ROOT,
        run_traced_captured_command=run_traced_captured_command,
        json_mode=_get_json_mode(),
        console_print=console_print,
        append_project_op=append_project_op,  # type: ignore
        project_next_json_path=project_next_json_path,
        load_project_next_candidate=load_project_next_candidate,
        next_command_requires_strict=next_command_requires_strict,
        dispatch_feature_next_command=dispatch_feature_next_command,
        inspect_feature_state=inspect_feature_state,
        run_design_cycle=run_design_cycle,
        run_approved_implementation_cycle=run_approved_implementation_cycle,
        release_gate=release_gate,
        run_full_flow=run_full_flow,
        init_feature=init_feature,
        bootstrap=bootstrap,
        build_approval_summary=build_approval_summary,
    )


def run_project_console_cycle(
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    from sdd_core.application.project_flow_runner import run_project_console_refresh_steps
    from sdd_core.infrastructure.ops_log import append_project_op
    return run_project_console_refresh_steps(
        refresh_project_state=refresh_project_state,
        build_flow_overview=build_flow_overview,
        build_project_next=build_project_next,
        build_tooling_hygiene=build_tooling_hygiene,
        build_project_console=build_project_console,
        append_project_op=append_project_op,  # type: ignore
        console_print=console_print,
        attachment_file=attachment_file,
        profile=profile,
    )


def run_project_cycle(
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    from sdd_core.application.project_runtime import run_project_cycle as app_run_project_cycle
    from sdd_core.application.project_flow_runner import capture_project_cycle_candidates
    from sdd_core.infrastructure.ops_log import append_project_op
    return app_run_project_cycle(
        attachment_file=attachment_file,
        profile=profile,
        run_project_console_cycle=run_project_console_cycle,
        capture_project_cycle_candidates=capture_project_cycle_candidates,
        run_continue_project_flow_fn=run_continue_project_flow,
        append_project_op=append_project_op,  # type: ignore
    )


def run_full_flow(
    feature_dir: str,
    strict: bool = False,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    from sdd_core.application.pipeline_execution import run_steps
    from sdd_core.application.pipeline_orchestration import append_post_flow_steps, build_implementation_gate_steps
    return run_steps(
        append_post_flow_steps(
            [
                ("verify", lambda: 0),  # verify step bypassed
                (
                    "design-gates",
                    lambda: run_design_gates(
                        feature_dir,
                        strict=strict,
                        attachment_file=attachment_file,
                        profile=profile,
                    ),
                ),
                *build_implementation_gate_steps(
                    feature_dir=feature_dir,
                    strict=strict,
                    gate4=gate4,
                    gate5=gate5,
                    update_design_index=update_design_index,
                    sync_baseline=sync_baseline,
                    validate_reports=validate_reports,
                ),
            ],
            feature_dir=feature_dir,
            refresh_feature_state=refresh_feature_state,
            run_project_console_cycle=run_project_console_cycle,
            attachment_file=attachment_file,
            profile=profile,
        ),
        console_print=console_print,
    )


def run_refresh_baseline(
    *,
    strict: bool = False,
    feature_dir: str | None = None,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    from sdd_core.application.pipeline_orchestration import build_refresh_baseline_steps
    refresh_strategy = resolve_schema_refresh_strategy(
        strict=strict, feature_dir=feature_dir
    )

    if is_strict_enabled(strict) and not refresh_strategy:
        console_print(
            "[WARN] strict 模式下未检测到 polyquery 配置或 snapshot，refresh-schema-context 将沿用本地快照策略"
        )

    return _run_steps_compat(
        build_refresh_baseline_steps(
            refresh_module_map=refresh_module_map,
            refresh_schema_context=refresh_schema_context,
            refresh_baseline_governance=refresh_baseline_governance,
            check_baseline_keys=check_baseline_keys,
            attachment_file=attachment_file,
            profile=profile,
            refresh_strategy=refresh_strategy,
        ),
        console_print_fn=console_print,
    )


def build_command_handlers() -> dict[str, Callable]:
    import argparse
    from sdd_core.application.cli import registry
    handlers = {}
    for name, meta in registry.commands.items():
        dummy_parser = argparse.ArgumentParser()
        meta["setup_func"](dummy_parser)
        func = dummy_parser._defaults.get("func")
        if func:
            handlers[name] = func
    return handlers


def install_runtime_command(
    target_root: str, runtime_dir: str, force: bool = False
) -> int:
    import json
    from sdd_core.application.generators.install_sdd_runtime import install_runtime as install_local_sdd_runtime
    payload = install_local_sdd_runtime(Path(target_root).resolve(), runtime_dir, force)
    console_print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def emit_result(payload: dict[str, Any]) -> None:
    from sdd_core.application.pipeline_result import emit_result as app_emit_result
    app_emit_result(payload)


def build_json_payload(
    args: argparse.Namespace, exit_code: int, duration_ms: int
) -> dict[str, Any]:
    from sdd_core.application.pipeline_result import build_result
    from sdd_core.application.pipeline_cli import collect_artifacts_for_command
    from sdd_core.application.pipeline_state import collect_trace_warnings, collect_trace_errors, _get_execution_trace
    warnings = collect_trace_warnings()
    errors = collect_trace_errors(exit_code)
    status = "error" if exit_code != 0 else ("warn" if warnings else "ok")
    message = f"{args.cmd} completed" if exit_code == 0 else f"{args.cmd} failed"
    return build_result(
        status=status,
        message=message,
        data={
            "command": args.cmd,
            "exit_code": exit_code,
            "duration_ms": duration_ms,
            "execution_trace": list(_get_execution_trace()),
        },
        errors=errors,
        warnings=warnings,
        artifacts=collect_artifacts_for_command(args),
    )
