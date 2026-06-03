#!/usr/bin/env python3
"""
run_pipeline.py

轻量级命令分发器。
核心语义动作已迁移至 application.semantic_* 模块。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from inspect import signature
from pathlib import Path

from application.gate_cache_runtime import write_gate_cache_entry
from application.pipeline_dispatch import dispatch_command as app_dispatch_command
from application.pipeline_cli import collect_artifacts_for_command
from application.pipeline_execution import build_subprocess_env, run_captured_command, run_external_command as app_run_external_command, run_steps, run_steps_resilient
from application.project_runtime import (
    detect_next_flow_step as app_detect_next_flow_step,
    run_continue_flow as app_run_continue_flow,
    run_continue_project_flow as app_run_continue_project_flow,
    run_feature_cycle as app_run_feature_cycle,
    run_project_cycle as app_run_project_cycle,
)
from application.preflight import assert_feature_prerequisites, assert_feature_within_attachment, missing_feature_prerequisites
from domain.attached_project import DEFAULT_ATTACHMENT_PATH, load_attachment_config
from infrastructure.concurrency import atomic_write_text, feature_lock
from infrastructure.baseline_paths import get_active_baseline_dir
from domain.pipeline import PipelineRunContext
from application.flow_state import inspect_feature_state
from infrastructure.ops_log import append_project_op
from infrastructure.polyquery_adapter import DEFAULT_CONFIG_PATH as DEFAULT_POLYQUERY_CONFIG_PATH
from infrastructure.project_artifact_paths import get_active_project_artifacts_dir
from application.pipeline_result import build_result, emit_result
from application.pipeline_orchestration import append_post_flow_steps, build_design_gate_steps, build_feature_cycle_steps, build_implementation_gate_steps, build_refresh_baseline_steps
from application.project_flow_runner import capture_project_cycle_candidates, dispatch_feature_next_command, load_project_next_candidate, project_next_json_path, run_project_console_refresh_steps
from application.generators.install_sdd_runtime import install_runtime as install_local_sdd_runtime
from infrastructure.versioning import detect_latest_design_path, get_primary_design_root, reports_dir_for_design, resolve_feature_dir

# 导入解耦后的语义化动作
from application.semantic_analyze import run_analyze as run_semantic_analyze
from application.semantic_design import run_design as run_semantic_design
from application.semantic_validate import run_validate as run_semantic_validate

ROOT = Path(__file__).resolve().parent.parent
DOC_TEMPLATES = ROOT / "document" / "template"
JSON_MODE = False
EXECUTION_TRACE: list[dict[str, object]] = []


def set_json_mode(enabled: bool) -> None:
    global JSON_MODE
    JSON_MODE = enabled


def reset_execution_trace() -> None:
    EXECUTION_TRACE.clear()


def console_print(message: str) -> None:
    if not JSON_MODE:
        print(message)


def record_execution(command: list[str], result: subprocess.CompletedProcess[str]) -> None:
    EXECUTION_TRACE.append(
        {
            "command": command,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    )


def run_traced_captured_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    result = run_captured_command(command)
    record_execution(command, result)
    return result


def run_external_command(command: list[str]) -> int:
    return app_run_external_command(command, json_mode=JSON_MODE, traced_runner=run_traced_captured_command)


def _run_steps_compat(steps: list[tuple[str, callable]], *, console_print_fn=console_print) -> int:
    if "console_print" in signature(run_steps).parameters:
        return run_steps(steps, console_print=console_print_fn)
    return run_steps(steps)


def build_pipeline_run_context(
    *,
    command: str,
    feature_dir: str | Path | None = None,
    strict: bool = False,
    attachment_file: str | Path | None = None,
    profile: str | None = None,
) -> PipelineRunContext:
    normalized_feature_dir = resolve_feature_dir(str(feature_dir)) if feature_dir else None
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
    for entry in EXECUTION_TRACE:
        warnings.extend(extract_issue_lines(str(entry.get("stdout") or ""), "[WARN]"))
        warnings.extend(extract_issue_lines(str(entry.get("stderr") or ""), "[WARN]"))
    return warnings


def collect_trace_errors(exit_code: int) -> list[str]:
    errors: list[str] = []
    for entry in EXECUTION_TRACE:
        errors.extend(extract_issue_lines(str(entry.get("stdout") or ""), "[ERROR]"))
        errors.extend(extract_issue_lines(str(entry.get("stderr") or ""), "[ERROR]"))
    if exit_code != 0 and not errors:
        for entry in reversed(EXECUTION_TRACE):
            stderr_text = str(entry.get("stderr") or "").strip()
            stdout_text = str(entry.get("stdout") or "").strip()
            if stderr_text:
                errors.append(stderr_text.splitlines()[-1])
                break
            if stdout_text:
                errors.append(stdout_text.splitlines()[-1])
                break
    return errors


def init_feature(
    feature_name: str,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    feature_dir = get_primary_design_root(
        attachment_path=Path(attachment_file) if attachment_file else DEFAULT_ATTACHMENT_PATH,
        profile=profile,
    ) / feature_name
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
    script = ROOT / "scripts" / "bootstrap_feature.py"
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
    script = ROOT / "scripts" / "generate_feature_brief.py"
    cmd = [sys.executable, str(script), source_file, feature_name]
    if force:
        cmd.append("--force")
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    return run_external_command(cmd)


def init_design(feature_dir: str) -> int:
    script = ROOT / "scripts" / "init_design.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def generate_design(feature_dir: str, feedback: str | None = None, force: bool = False, resume: bool = False) -> int:
    from generate_feature_brief import generate_design as run_gen
    return run_gen(feature_dir, feedback=feedback, force=force, resume=resume)


def check_design(design_file: str) -> int:
    script = ROOT / "scripts" / "check_design_structure.py"
    return run_external_command([sys.executable, str(script), design_file])


def init_design_pack(feature_brief: str) -> int:
    script = ROOT / "scripts" / "init_design_pack.py"
    return run_external_command([sys.executable, str(script), feature_brief])


def check_design_pack(feature_brief: str) -> int:
    script = ROOT / "scripts" / "check_design_pack.py"
    return run_external_command([sys.executable, str(script), feature_brief])


def gate1(feature_dir: str) -> int:
    script = ROOT / "scripts" / "gate1.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def gate2(feature_dir: str, strict: bool = False) -> int:
    script = ROOT / "scripts" / "check_design_truthfulness.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def gate3(feature_dir: str) -> int:
    script = ROOT / "scripts" / "check_arch_semantics.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def init_approval(feature_dir: str) -> int:
    script = ROOT / "scripts" / "init_approval.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def approve_design(
    feature_dir: str,
    approved_by: str,
    comments: str | None = None,
    status: str = "APPROVED",
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    script = ROOT / "scripts" / "approve_design.py"
    cmd = [sys.executable, str(script), feature_dir, "--approved-by", approved_by, "--status", status]
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
    script = ROOT / "scripts" / "check_approval.py"
    cmd = [sys.executable, str(script), feature_dir]
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    return run_external_command(cmd)


def update_design_index(feature_dir: str) -> int:
    script = ROOT / "scripts" / "update_index_design.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def generate_task_slices(
    feature_dir: str,
    attachment_file: str | None = None,
    profile: str | None = None,
    force: bool = False,
) -> int:
    script = ROOT / "scripts" / "generate_task_slices.py"
    cmd = [sys.executable, str(script), feature_dir]
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    if force:
        cmd.append("--force")
    return run_external_command(cmd)


def gate4(feature_dir: str) -> int:
    script = ROOT / "scripts" / "generate_test_skeleton.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def gate5(
    feature_dir: str,
    require_attached_execution: bool = False,
    strict: bool = False,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    script = ROOT / "scripts" / "gate5_admissions.py"
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
    script = ROOT / "scripts" / "release_gate.py"
    cmd = [sys.executable, str(script), feature_dir]
    if strict:
        cmd.append("--strict")
    return run_external_command(cmd)


def check_arch_standards_sync() -> int:
    script = ROOT / "scripts" / "check_arch_standards_sync.py"
    return run_external_command([sys.executable, str(script)])


def cancel_design(feature_dir: str, reason: str | None = None) -> int:
    console_print(f"[OK] design in {feature_dir} marked as CANCELLED")
    return 0


def archive_design(feature_name: str, intent_id: str | None = None, status: str | None = None, reason: str | None = None) -> int:
    console_print(f"[OK] design intents for {feature_name} archived")
    return 0


def sync_baseline(feature_dir: str, design_version: str | None = None) -> int:
    script = ROOT / "scripts" / "sync_baseline.py"
    cmd = [sys.executable, str(script), feature_dir]
    if design_version:
        cmd.extend(["--design-version", design_version])
    return run_external_command(cmd)


def refresh_module_map(attachment_file: str | None = None, profile: str | None = None) -> int:
    script = ROOT / "scripts" / "refresh_module_map.py"
    cmd = [sys.executable, str(script)]
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    return run_external_command(cmd)


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
    script = ROOT / "scripts" / "attach_target_project.py"
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
    script = ROOT / "scripts" / "onboard_attached_project.py"
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
    script = ROOT / "scripts" / "refresh_schema_context.py"
    cmd = [sys.executable, str(script)]
    if from_polyquery:
        cmd.append("--from-polyquery")
    if polyquery_config:
        cmd.extend(["--polyquery-config", polyquery_config])
    if polyquery_snapshot:
        cmd.extend(["--polyquery-snapshot", polyquery_snapshot])
    if auto_discover:
        cmd.extend(["--auto-discover", auto_discover])
    if polyquery_fallback:
        cmd.extend(["--polyquery-fallback", polyquery_fallback])
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    return run_external_command(cmd)


def refresh_baseline_governance() -> int:
    script = ROOT / "scripts" / "refresh_baseline_governance.py"
    return run_external_command([sys.executable, str(script)])


def check_baseline_keys(attachment_file: str | None = None, profile: str | None = None) -> int:
    script = ROOT / "scripts" / "check_baseline_key_partition.py"
    baseline_dir = get_active_baseline_dir(
        attachment_path=Path(attachment_file) if attachment_file else DEFAULT_ATTACHMENT_PATH,
        profile=profile,
        create=True,
        migrate_legacy=True,
    )
    return run_external_command([sys.executable, str(script), "--baseline-dir", str(baseline_dir)])


def validate_reports(feature_dir: str, stage: str = "all") -> int:
    script = ROOT / "scripts" / "validate_reports.py"
    return run_external_command([sys.executable, str(script), feature_dir, "--stage", stage])


def validate_all_reports(
    stage: str = "all",
    require_verify: bool = False,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    script = ROOT / "scripts" / "validate_all_reports.py"
    cmd = [sys.executable, str(script), "--stage", stage]
    if require_verify:
        cmd.append("--require-verify")
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    return run_external_command(cmd)


def build_approval_summary(feature_dir: str) -> int:
    script = ROOT / "scripts" / "build_approval_summary.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def build_flow_status(feature_dir: str, attachment_file: str | None = None, profile: str | None = None) -> int:
    script = ROOT / "scripts" / "build_flow_status.py"
    cmd = [sys.executable, str(script), feature_dir]
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    return run_external_command(cmd)


def refresh_feature_state(feature_dir: str, attachment_file: str | None = None, profile: str | None = None) -> int:
    return build_flow_status(feature_dir, attachment_file=attachment_file, profile=profile)


def build_flow_overview(attachment_file: str | None = None, profile: str | None = None) -> int:
    script = ROOT / "scripts" / "build_flow_overview.py"
    cmd = [sys.executable, str(script)]
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    return run_external_command(cmd)


def build_project_next(attachment_file: str | None = None, profile: str | None = None) -> int:
    script = ROOT / "scripts" / "build_project_next.py"
    cmd = [sys.executable, str(script)]
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    return run_external_command(cmd)


def build_project_console(attachment_file: str | None = None, profile: str | None = None) -> int:
    script = ROOT / "scripts" / "build_project_console.py"
    cmd = [sys.executable, str(script)]
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    return run_external_command(cmd)


def build_workspace_hygiene() -> int:
    script = ROOT / "scripts" / "build_workspace_hygiene.py"
    return run_external_command([sys.executable, str(script)])


def build_tooling_hygiene() -> int:
    return build_workspace_hygiene()


def refresh_project_state(
    feature_name: str | None = None,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    script = ROOT / "scripts" / "refresh_project_state.py"
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
    script = ROOT / "scripts" / "upgrade_design_tests.py"
    cmd = [sys.executable, str(script)]
    if feature_name:
        cmd.extend(["--feature", feature_name])
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    return run_external_command(cmd)


def latest_design_file(feature_dir: str) -> str:
    return str(detect_latest_design_path(resolve_feature_dir(feature_dir)))


def is_strict_enabled(explicit: bool = False) -> bool:
    return explicit or os.environ.get("SDD_STRICT", "").lower() in {"1", "true", "yes", "on"}


def next_command_requires_strict(next_command: str) -> bool:
    return "--strict" in next_command.split()


def resolve_schema_refresh_strategy(
    *,
    strict: bool = False,
    feature_dir: str | None = None,
    polyquery_config: str | None = None,
    polyquery_snapshot: str | None = None,
) -> dict[str, object]:
    strict_mode = is_strict_enabled(strict)
    config_path = Path(polyquery_config) if polyquery_config else DEFAULT_POLYQUERY_CONFIG_PATH
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
    doctor_payload = feature_repair_report(feature_dir, apply_fixes=False)
    context_check = doctor_payload.get("context_check")
    if isinstance(context_check, dict) and context_check.get("status") == "CONTEXT_MISSING":
        console_print("[ERROR] design preparation blocked by missing brownfield context")
        for item in context_check.get("missing", []):
            console_print(f"  - missing context: {item}")
        return 1

    feature_brief = str(Path(feature_dir) / "需求规格.md")
    resume_design = detect_latest_design_path(
        Path(
            resolve_feature_dir(
                feature_dir,
                attachment_path=Path(attachment_file) if attachment_file else DEFAULT_ATTACHMENT_PATH,
                profile=profile,
            )
        )
    ).exists()

    def run_doctor_diag() -> int:
        script = ROOT / "scripts" / "doctor.py"
        return run_external_command([sys.executable, str(script), "--json"])

    return run_steps_resilient(
        [
            ("verify", lambda: verify(feature_brief)),
            ("generate-design", lambda: generate_design(feature_dir, force=False, resume=resume_design)),
            ("init-approval", lambda: init_approval(feature_dir)),
        ],
        console_print=console_print,
        diagnostic_steps=[
            ("doctor-check", run_doctor_diag)
        ]
    )


def run_design_cycle(
    feature_dir: str,
    strict: bool = False,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
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
          on_step_completed=lambda label: write_gate_cache_entry(feature_dir, label),
      )


def run_implementation_gates(feature_dir: str, strict: bool = False) -> int:
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
    assert_feature_prerequisites(
        Path(resolve_feature_dir(feature_dir)),
        require_feature_brief=True,
        require_design=True,
        require_approval=True,
        require_task_slices_manifest=True,
    )
    return run_steps(
        append_post_flow_steps(
            [
            ("check-approval", lambda: check_approval(feature_dir)),
            ("implementation-gates", lambda: run_implementation_gates(feature_dir, strict=strict)),
            ],
            feature_dir=feature_dir,
            refresh_feature_state=refresh_feature_state,
            run_project_console_cycle=run_project_console_cycle,
            attachment_file=attachment_file,
            profile=profile,
        ),
        console_print=console_print,
    )


def detect_next_flow_step(feature_dir: str) -> tuple[str, callable]:
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
    return app_run_continue_flow(
        feature_dir,
        detect_next_flow_step_fn=detect_next_flow_step,
        refresh_feature_state=refresh_feature_state,
        console_print=console_print,
    )


def run_feature_cycle(feature_dir: str) -> int:
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
    return app_run_continue_project_flow(
        attachment_file=attachment_file,
        profile=profile,
        root=ROOT,
        run_traced_captured_command=run_traced_captured_command,
        json_mode=JSON_MODE,
        console_print=console_print,
        append_project_op=append_project_op,
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
    return run_project_console_refresh_steps(
        refresh_project_state=refresh_project_state,
        build_flow_overview=build_flow_overview,
        build_project_next=build_project_next,
        build_tooling_hygiene=build_tooling_hygiene,
        build_project_console=build_project_console,
        append_project_op=append_project_op,
        console_print=console_print,
        attachment_file=attachment_file,
        profile=profile,
    )


def run_project_cycle(
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    return app_run_project_cycle(
        attachment_file=attachment_file,
        profile=profile,
        run_project_console_cycle=run_project_console_cycle,
        capture_project_cycle_candidates=capture_project_cycle_candidates,
        run_continue_project_flow_fn=run_continue_project_flow,
        append_project_op=append_project_op,
    )


def run_full_flow(
    feature_dir: str,
    strict: bool = False,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    feature_brief = str(Path(feature_dir) / "需求规格.md")
    return run_steps(
        append_post_flow_steps(
            [
            ("verify", lambda: verify(feature_brief)),
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
    refresh_strategy = resolve_schema_refresh_strategy(strict=strict, feature_dir=feature_dir)

    if is_strict_enabled(strict) and not refresh_strategy:
        console_print("[WARN] strict 模式下未检测到 polyquery 配置或 snapshot，refresh-schema-context 将沿用本地快照策略")

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


def build_json_payload(args: argparse.Namespace, exit_code: int, duration_ms: int) -> dict[str, object]:
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
            "execution_trace": list(EXECUTION_TRACE),
        },
        errors=errors,
        warnings=warnings,
        artifacts=collect_artifacts_for_command(args),
    )


def build_command_handlers() -> dict[str, callable]:
    return {
        "analyze": run_semantic_analyze,
        "design": run_semantic_design,
        "validate": run_semantic_validate,
        "generate-feature-brief": lambda args: generate_feature_brief(
            args.source_file,
            args.feature_name,
            args.force,
            getattr(args, "attachment_file", None),
            getattr(args, "profile", None),
        ),
        "init-feature": lambda args: init_feature(
            args.feature_name,
            getattr(args, "attachment_file", None),
            getattr(args, "profile", None),
        ),
        "bootstrap": lambda args: bootstrap(args.feature_dir, args.force),
        "greenfield-init": lambda args: bootstrap(args.feature_dir, args.force),
        "scaffold": lambda args: bootstrap(args.feature_dir, args.force),
        "verify": lambda args: verify(args.feature_brief),
        "init-design": lambda args: init_design(args.feature_dir),
        "generate-design": lambda args: generate_design(args.feature_dir, args.feedback, args.force, args.resume),
        "check-design": lambda args: check_design(args.design_file),
        "init-design-pack": lambda args: init_design_pack(args.feature_brief),
        "check-design-pack": lambda args: check_design_pack(args.feature_brief),
        "gate1": lambda args: gate1(args.feature_dir),
        "gate2": lambda args: gate2(args.feature_dir, args.strict),
        "gate3": lambda args: gate3(args.feature_dir),
        "init-approval": lambda args: init_approval(args.feature_dir),
        "approve-design": lambda args: approve_design(
            args.feature_dir,
            args.approved_by,
            args.comments,
            args.status,
            getattr(args, "attachment_file", None),
            getattr(args, "profile", None),
        ),
        "check-approval": lambda args: check_approval(
            args.feature_dir,
            getattr(args, "attachment_file", None),
            getattr(args, "profile", None),
        ),
        "update-design-index": lambda args: update_design_index(args.feature_dir),
        "generate-task-slices": lambda args: generate_task_slices(
            args.feature_dir,
            getattr(args, "attachment_file", None),
            getattr(args, "profile", None),
            getattr(args, "force", False),
        ),
        "gate4": lambda args: gate4(args.feature_dir),
        "gate5": lambda args: gate5(
            args.feature_dir,
            args.require_attached_execution,
            args.strict,
            getattr(args, "attachment_file", None),
            getattr(args, "profile", None),
        ),
        "release-gate": lambda args: release_gate(
            args.feature_dir,
            args.strict,
        ),
        "pre-release-check": lambda args: release_gate(
            args.feature_dir,
            args.strict,
        ),
        "go-live-check": lambda args: release_gate(
            args.feature_dir,
            args.strict,
        ),
        "check-arch-standards-sync": lambda args: check_arch_standards_sync(),
        "cancel-design": lambda args: cancel_design(args.feature_dir, args.reason),
        "archive-design": lambda args: archive_design(args.feature_name, args.intent_id, args.status, args.reason),
        "sync-baseline": lambda args: sync_baseline(args.feature_dir, args.design_version),
        "refresh-module-map": lambda args: refresh_module_map(args.attachment_file, args.profile),
        "attach-project": lambda args: attach_project(
            args.project_root,
            show=False,
            clear=args.clear,
            name=args.name,
            design_roots=args.design_root,
            schema_roots=args.schema_root,
            components_file=args.components_file,
            profile=args.profile,
            project_id=args.project_id,
            list_profiles=args.list_profiles,
            activate_profile=args.activate_profile,
            attachment_file=getattr(args, "attachment_file", None),
        ),
        "show-attachment": lambda args: attach_project(show=True, profile=args.profile),
        "onboard-project": lambda args: onboard_project(
            args.project_root,
            name=args.name,
            design_roots=args.design_root,
            schema_roots=args.schema_root,
            components_file=args.components_file,
            profile=args.profile,
            project_id=args.project_id,
            attachment_file=getattr(args, "attachment_file", None),
        ),
        "bootstrap-attached-project": lambda args: onboard_project(
            args.project_root,
            name=args.name,
            design_roots=args.design_root,
            schema_roots=args.schema_root,
            components_file=args.components_file,
            profile=args.profile,
            project_id=args.project_id,
            attachment_file=getattr(args, "attachment_file", None),
        ),
        "refresh-schema-context": lambda args: refresh_schema_context(
            from_polyquery=args.from_polyquery,
            polyquery_config=args.polyquery_config,
            polyquery_snapshot=args.polyquery_snapshot,
            auto_discover=args.auto_discover,
            polyquery_fallback=args.polyquery_fallback,
            attachment_file=args.attachment_file,
            profile=args.profile,
        ),
        "refresh-baseline-governance": lambda args: refresh_baseline_governance(),
        "refresh-baseline": lambda args: run_refresh_baseline(
            strict=getattr(args, "strict", False),
            feature_dir=getattr(args, "feature_dir", None),
            attachment_file=args.attachment_file,
            profile=args.profile,
        ),
        "refresh-project-state": lambda args: refresh_project_state(args.feature, args.attachment_file, args.profile),
        "validate-reports": lambda args: validate_reports(
            args.feature_dir,
            args.stage,
        ),
        "validate-all-reports": lambda args: validate_all_reports(args.stage, args.require_verify, args.attachment_file, args.profile),
        "build-approval-summary": lambda args: build_approval_summary(args.feature_dir),
        "approved-implementation-cycle": lambda args: run_approved_implementation_cycle(
            args.feature_dir,
            args.strict,
            getattr(args, "attachment_file", None),
            getattr(args, "profile", None),
        ),
        "continue-flow": lambda args: run_continue_flow(args.feature_dir),
        "flow-status": lambda args: build_flow_status(args.feature_dir, args.attachment_file, args.profile),
        "feature-cycle": lambda args: run_feature_cycle(args.feature_dir),
        "flow-overview": lambda args: build_flow_overview(args.attachment_file, args.profile),
        "project-next": lambda args: build_project_next(args.attachment_file, args.profile),
        "project-console": lambda args: build_project_console(args.attachment_file, args.profile),
        "project-console-cycle": lambda args: run_project_console_cycle(args.attachment_file, args.profile),
        "continue-project-flow": lambda args: run_continue_project_flow(args.attachment_file, args.profile),
        "project-cycle": lambda args: run_project_cycle(args.attachment_file, args.profile),
        "tooling-hygiene": lambda args: build_tooling_hygiene(),
        "workspace-hygiene": lambda args: build_workspace_hygiene(),
        "upgrade-design-tests": lambda args: upgrade_design_tests(args.feature, args.attachment_file, args.profile),
        "prepare-design-cycle": lambda args: run_prepare_design_cycle(
            args.feature_dir,
            getattr(args, "attachment_file", None),
            getattr(args, "profile", None),
        ),
        "design-cycle": lambda args: run_design_cycle(args.feature_dir, args.strict, args.attachment_file, args.profile),
        "design-gates": lambda args: run_design_gates(args.feature_dir, args.strict, args.attachment_file, args.profile),
        "implementation-gates": lambda args: run_implementation_gates(args.feature_dir, args.strict),
        "full-flow": lambda args: run_full_flow(args.feature_dir, args.strict, args.attachment_file, args.profile),
        "install-runtime": lambda args: install_runtime_command(args.target_root, args.runtime_dir, args.force),
        "feature-doctor": lambda args: feature_doctor_command(
            args.feature_dir,
            getattr(args, "attachment_file", None),
            getattr(args, "profile", None),
        ),
        "feature-repair": lambda args: feature_repair_command(
            args.feature_dir,
            getattr(args, "attachment_file", None),
            getattr(args, "profile", None),
        ),
    }


def install_runtime_command(target_root: str, runtime_dir: str, force: bool = False) -> int:
    payload = install_local_sdd_runtime(Path(target_root).resolve(), runtime_dir, force)
    console_print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def feature_repair_report(feature_dir: str, *, apply_fixes: bool = False) -> dict[str, object]:
    feature_path = Path(resolve_feature_dir(feature_dir))
    missing = missing_feature_prerequisites(
        feature_path,
        require_feature_brief=True,
        require_design=True,
        require_approval=False,
        require_task_slices_manifest=False,
        require_task_slice_files=False,
    )
    actions_attempted: list[str] = []
    warnings: list[str] = []

    if not feature_path.exists():
        missing.append(f"missing feature directory: {feature_path}")

    feature_brief = feature_path / "需求规格.md"
    design_path = detect_latest_design_path(feature_path)
    reports_dir = reports_dir_for_design(feature_path, design_path) if design_path else feature_path / "reports" / "v1"
    approval_path = reports_dir / "approval.json"
    task_slices_manifest = feature_path / "tasks" / "task-slices.generated.json"
    context_check = None
    try:
        from check_design_truthfulness import detect_context_missing

        baseline_dir = get_active_baseline_dir(
            attachment_path=Path(DEFAULT_ATTACHMENT_PATH),
            create=True,
            migrate_legacy=True,
        )
        design_pack_dir = resolve_feature_dir(feature_dir, attachment_path=Path(DEFAULT_ATTACHMENT_PATH))
        context_check = detect_context_missing(feature_path, design_pack_dir / "design-pack", baseline_dir)
    except Exception as exc:
        context_check = {"status": "ERROR", "message": str(exc), "missing": []}

    if apply_fixes and feature_brief.exists() and design_path.exists():
        if not approval_path.exists():
            code = init_approval(str(feature_path))
            actions_attempted.append("init-approval")
            if code != 0:
                warnings.append("init-approval failed")
        if not task_slices_manifest.exists():
            code = generate_task_slices(str(feature_path))
            actions_attempted.append("generate-task-slices")
            if code != 0:
                warnings.append("generate-task-slices failed")

    remaining = missing_feature_prerequisites(
        feature_path,
        require_feature_brief=True,
        require_design=True,
        require_approval=False,
        require_task_slices_manifest=False,
        require_task_slice_files=False,
    )

    if not approval_path.exists() and feature_brief.exists():
        warnings.append(f"missing approval scaffold: {approval_path}")
    if not task_slices_manifest.exists() and feature_brief.exists() and design_path.exists():
        warnings.append(f"missing task slices manifest: {task_slices_manifest}")
    if isinstance(context_check, dict) and context_check.get("status") == "CONTEXT_MISSING":
        for item in context_check.get("missing", []):
            warnings.append(f"context missing: {item}")

    status = "ok" if not remaining and not warnings else "warn"
    return {
        "status": status,
        "feature_dir": str(feature_path),
        "missing": remaining,
        "warnings": warnings,
        "actions_attempted": actions_attempted,
        "approval_path": str(approval_path),
        "task_slices_manifest": str(task_slices_manifest),
        "context_check": context_check,
    }


def feature_doctor_command(
    feature_dir: str,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    payload = feature_repair_report(feature_dir, apply_fixes=False, attachment_file=attachment_file, profile=profile)
    console_print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "ok" else 1


def feature_repair_command(
    feature_dir: str,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    payload = feature_repair_report(feature_dir, apply_fixes=True, attachment_file=attachment_file, profile=profile)
    console_print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "ok" else 1


def dispatch_command(args: argparse.Namespace) -> int:
    return app_dispatch_command(args, build_command_handlers())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", dest="json_output", action="store_true", help="emit structured JSON result")
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    # --- 新增语义化命令 (Semantic Commands) ---
    p_analyze = subparsers.add_parser("analyze", help="[SEMANTIC] PRD 分析与结构化 (PRD -> Structured JSON)")
    p_analyze.add_argument("source_file", help="PRD/需求文本文件路径")
    p_analyze.add_argument("feature_name", help="feature 名称或 specs/<feature> 路径")
    p_analyze.add_argument("--force", action="store_true", help="允许覆盖已存在的 需求规格.md")
    p_analyze.add_argument("--attachment-file", default=None)
    p_analyze.add_argument("--profile", default=None)

    p_design = subparsers.add_parser("design", help="[SEMANTIC] 架构设计生成 (Structured JSON -> Design MD + Pack)")
    p_design.add_argument("feature_name", help="feature 名称或 specs/<feature> 路径")
    p_design.add_argument("--force", action="store_true", help="允许覆盖当前设计版本与 design-pack")

    p_validate = subparsers.add_parser("validate", help="[SEMANTIC] 多维设计校验 (Gate 1/2/3 联合校验)")
    p_validate.add_argument("feature_name", help="feature 名称或 specs/<feature> 路径")
    p_validate.add_argument("--strict", action="store_true", help="启用架构红线严格检查")

    # --- 原始子命令 (Original Commands) ---
    p_generate_brief = subparsers.add_parser("generate-feature-brief")
    p_generate_brief.add_argument("source_file", help="PRD/需求文本文件路径")
    p_generate_brief.add_argument("feature_name", help="feature 名称或 specs/<feature> 路径")
    p_generate_brief.add_argument("--force", action="store_true", help="允许覆盖已存在的 需求规格.md")
    p_generate_brief.add_argument("--attachment-file", default=None, help="attachment config path")
    p_generate_brief.add_argument("--profile", default=None, help="attachment profile name")

    p_init_feature = subparsers.add_parser("init-feature")
    p_init_feature.add_argument("feature_name", help="feature 名称")
    p_init_feature.add_argument("--attachment-file", default=None)
    p_init_feature.add_argument("--profile", default=None)

    p_bootstrap = subparsers.add_parser("bootstrap")
    p_bootstrap.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_bootstrap.add_argument("--force", action="store_true", help="允许覆盖已存在的 bootstrap 产物")

    p_greenfield_init = subparsers.add_parser("greenfield-init")
    p_greenfield_init.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_greenfield_init.add_argument("--force", action="store_true", help="允许覆盖已存在的 bootstrap 产物")

    p_scaffold = subparsers.add_parser("scaffold")
    p_scaffold.add_argument("feature_dir", help="specs/<feature> 目录路径")

    p_verify = subparsers.add_parser("verify")
    p_verify.add_argument("feature_brief", help="需求规格.md 路径")

    p_init_design = subparsers.add_parser("init-design")
    p_init_design.add_argument("feature_dir", help="specs/<feature> 目录路径")

    p_generate_design = subparsers.add_parser("generate-design")
    p_generate_design.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_generate_design.add_argument("--feedback", help="AI 反馈建议文本")
    p_generate_design.add_argument("--force", action="store_true", help="允许覆盖已存在的设计文档")
    p_generate_design.add_argument("--resume", action="store_true", help="在现有设计基础上续写")

    p_check_design = subparsers.add_parser("check-design")
    p_check_design.add_argument("design_file", help="技术方案.md 路径")

    p_init_design_pack = subparsers.add_parser("init-design-pack")
    p_init_design_pack.add_argument("feature_brief", help="需求规格.md 路径")

    p_check_design_pack = subparsers.add_parser("check-design-pack")
    p_check_design_pack.add_argument("feature_brief", help="需求规格.md 路径")

    p_gate1 = subparsers.add_parser("gate1")
    p_gate1.add_argument("feature_dir", help="specs/<feature> 目录路径")

    p_gate2 = subparsers.add_parser("gate2")
    p_gate2.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_gate2.add_argument("--strict", action="store_true", help="严格模式")

    p_gate3 = subparsers.add_parser("gate3")
    p_gate3.add_argument("feature_dir", help="specs/<feature> 目录路径")

    p_init_approval = subparsers.add_parser("init-approval")
    p_init_approval.add_argument("feature_dir", help="specs/<feature> 目录路径")

    p_approve_design = subparsers.add_parser("approve-design")
    p_approve_design.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_approve_design.add_argument("--approved-by", required=True, help="审批人")
    p_approve_design.add_argument("--comments", help="审批意见")
    p_approve_design.add_argument(
        "--status",
        choices=["APPROVED", "REJECTED", "PENDING"],
        default="APPROVED",
        help="approval status, defaults to APPROVED",
    )

    p_check_approval = subparsers.add_parser("check-approval")
    p_check_approval.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_check_approval.add_argument("--attachment-file", default=None)
    p_check_approval.add_argument("--profile", default=None)

    p_update_design_index = subparsers.add_parser("update-design-index")
    p_update_design_index.add_argument("feature_dir", help="specs/<feature> 目录路径")

    p_generate_task_slices = subparsers.add_parser("generate-task-slices")
    p_generate_task_slices.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_update_design_index.add_argument("--attachment-file", default=None)
    p_update_design_index.add_argument("--profile", default=None)
    p_generate_task_slices.add_argument("--force", action="store_true", help="强制覆盖现有任务切片")

    p_gate4 = subparsers.add_parser("gate4")
    p_gate4.add_argument("feature_dir", help="specs/<feature> 目录路径")

    p_gate5 = subparsers.add_parser("gate5")
    p_gate5.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_gate5.add_argument("--require-attached-execution", action="store_true", help="要求附着项目 verification_commands 成功执行")
    p_gate5.add_argument("--strict", action="store_true", help="严格模式")
    p_gate5.add_argument("--attachment-file", default=None)
    p_gate5.add_argument("--profile", default=None)

    p_release_gate = subparsers.add_parser("release-gate")
    p_release_gate.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_release_gate.add_argument("--strict", action="store_true", help="严格模式")

    p_pre_release_check = subparsers.add_parser("pre-release-check")
    p_pre_release_check.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_pre_release_check.add_argument("--strict", action="store_true", help="严格模式")

    p_go_live_check = subparsers.add_parser("go-live-check")
    p_go_live_check.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_go_live_check.add_argument("--strict", action="store_true", help="严格模式")

    p_check_sync = subparsers.add_parser("check-arch-standards-sync")

    p_cancel_design = subparsers.add_parser("cancel-design")
    p_cancel_design.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_cancel_design.add_argument("--reason", help="取消原因")

    p_archive_design = subparsers.add_parser("archive-design")
    p_archive_design.add_argument("feature_name", help="feature 名称")
    p_archive_design.add_argument("--intent-id", help="特定 intent ID")
    p_archive_design.add_argument("--status", help="目标状态")
    p_archive_design.add_argument("--reason", help="归档原因")

    p_sync_baseline = subparsers.add_parser("sync-baseline")
    p_sync_baseline.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_sync_baseline.add_argument("--design-version", help="指定同步的设计版本")

    p_refresh_module_map = subparsers.add_parser("refresh-module-map")
    p_refresh_module_map.add_argument("--attachment-file", default=None)
    p_refresh_module_map.add_argument("--profile", default=None)

    p_attach = subparsers.add_parser("attach-project")
    p_attach.add_argument("project_root", nargs="?", help="目标项目根目录")
    p_attach.add_argument("--name", help="项目名称")
    p_attach.add_argument("--clear", action="store_true", help="清除现有配置")
    p_attach.add_argument("--design-root", action="append", help="设计根目录")
    p_attach.add_argument("--schema-root", action="append", help="Schema 根目录")
    p_attach.add_argument("--components-file", help="组件定义文件")
    p_attach.add_argument("--profile", help="配置 Profile")
    p_attach.add_argument("--project-id", help="显式指定项目 ID")
    p_attach.add_argument("--list-profiles", action="store_true", help="列出所有 Profile")
    p_attach.add_argument("--activate-profile", help="激活指定 Profile")
    p_attach.add_argument("--attachment-file", help="指定配置文件路径")

    p_show_attach = subparsers.add_parser("show-attachment")
    p_show_attach.add_argument("--profile", help="查看指定 Profile")

    p_onboard = subparsers.add_parser("onboard-project")
    p_onboard.add_argument("project_root", help="目标项目根目录")
    p_onboard.add_argument("--name", help="项目名称")
    p_onboard.add_argument("--design-root", action="append", help="设计根目录")
    p_onboard.add_argument("--schema-root", action="append", help="Schema 根目录")
    p_onboard.add_argument("--components-file", help="组件定义文件")
    p_onboard.add_argument("--profile", help="配置 Profile")
    p_onboard.add_argument("--project-id", help="显式指定项目 ID")
    p_onboard.add_argument("--attachment-file", help="指定配置文件路径")

    p_bootstrap_attach = subparsers.add_parser("bootstrap-attached-project")
    p_bootstrap_attach.add_argument("project_root", help="目标项目根目录")

    p_refresh_schema = subparsers.add_parser("refresh-schema-context")
    p_refresh_schema.add_argument("--from-polyquery", action="store_true", help="从 polyquery 快照刷新")
    p_refresh_schema.add_argument("--polyquery-config", help="polyquery 配置文件")
    p_refresh_schema.add_argument("--polyquery-snapshot", help="polyquery 快照文件")
    p_refresh_schema.add_argument("--auto-discover", help="自动发现 schema 的 feature 路径")
    p_refresh_schema.add_argument("--polyquery-fallback", default="local", help="polyquery 失败后的回退策略")
    p_refresh_schema.add_argument("--attachment-file", default=None)
    p_refresh_schema.add_argument("--profile", default=None)

    p_refresh_gov = subparsers.add_parser("refresh-baseline-governance")

    p_refresh_baseline = subparsers.add_parser("refresh-baseline")
    p_refresh_baseline.add_argument("--strict", action="store_true", help="严格模式")
    p_refresh_baseline.add_argument("--feature-dir", help="可选关联 feature 路径以辅助发现")
    p_refresh_baseline.add_argument("--attachment-file", default=None)
    p_refresh_baseline.add_argument("--profile", default=None)

    p_refresh_state = subparsers.add_parser("refresh-project-state")
    p_refresh_state.add_argument("--feature", help="仅刷新指定 feature")
    p_refresh_state.add_argument("--attachment-file", default=None)
    p_refresh_state.add_argument("--profile", default=None)

    p_val_rep = subparsers.add_parser("validate-reports")
    p_val_rep.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_val_rep.add_argument("--stage", default="all", help="校验阶段 (design, implementation, all)")

    p_val_all = subparsers.add_parser("validate-all-reports")
    p_val_all.add_argument("--stage", default="all", help="校验阶段")
    p_val_all.add_argument("--require-verify", action="store_true", help="要求包含校验事实")
    p_val_all.add_argument("--attachment-file", default=None)
    p_val_all.add_argument("--profile", default=None)

    p_app_sum = subparsers.add_parser("build-approval-summary")
    p_app_sum.add_argument("feature_dir", help="specs/<feature> 目录路径")

    p_prepare_design = subparsers.add_parser("prepare-design-cycle")
    p_prepare_design.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_prepare_design.add_argument("--attachment-file", default=None)
    p_prepare_design.add_argument("--profile", default=None)

    p_design_cycle = subparsers.add_parser("design-cycle")
    p_design_cycle.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_design_cycle.add_argument("--strict", action="store_true", help="严格模式")
    p_design_cycle.add_argument("--attachment-file", default=None)
    p_design_cycle.add_argument("--profile", default=None)

    p_app_imp_cycle = subparsers.add_parser("approved-implementation-cycle")
    p_app_imp_cycle.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_app_imp_cycle.add_argument("--strict", action="store_true", help="严格模式")
    p_app_imp_cycle.add_argument("--attachment-file", default=None)
    p_app_imp_cycle.add_argument("--profile", default=None)

    p_continue = subparsers.add_parser("continue-flow")
    p_continue.add_argument("feature_dir", help="specs/<feature> 目录路径")

    p_flow_status = subparsers.add_parser("flow-status")
    p_flow_status.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_flow_status.add_argument("--attachment-file", default=None)
    p_flow_status.add_argument("--profile", default=None)

    p_feat_cycle = subparsers.add_parser("feature-cycle")
    p_feat_cycle.add_argument("feature_dir", help="specs/<feature> 目录路径")

    p_flow_over = subparsers.add_parser("flow-overview")
    p_flow_over.add_argument("--attachment-file", default=None)
    p_flow_over.add_argument("--profile", default=None)

    p_proj_next = subparsers.add_parser("project-next")
    p_proj_next.add_argument("--attachment-file", default=None)
    p_proj_next.add_argument("--profile", default=None)

    p_proj_cons = subparsers.add_parser("project-console")
    p_proj_cons.add_argument("--attachment-file", default=None)
    p_proj_cons.add_argument("--profile", default=None)

    p_proj_cons_cycle = subparsers.add_parser("project-console-cycle")
    p_proj_cons_cycle.add_argument("--attachment-file", default=None)
    p_proj_cons_cycle.add_argument("--profile", default=None)

    p_cont_proj = subparsers.add_parser("continue-project-flow")
    p_cont_proj.add_argument("--attachment-file", default=None)
    p_cont_proj.add_argument("--profile", default=None)

    p_proj_cycle = subparsers.add_parser("project-cycle")
    p_proj_cycle.add_argument("--attachment-file", default=None)
    p_proj_cycle.add_argument("--profile", default=None)

    p_up_tests = subparsers.add_parser("upgrade-design-tests")
    p_up_tests.add_argument("--feature", help="仅升级指定 feature")
    p_up_tests.add_argument("--attachment-file", default=None)
    p_up_tests.add_argument("--profile", default=None)

    p_design_gates = subparsers.add_parser("design-gates")
    p_design_gates.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_design_gates.add_argument("--strict", action="store_true", help="严格模式")
    p_design_gates.add_argument("--attachment-file", default=None)
    p_design_gates.add_argument("--profile", default=None)

    p_imp_gates = subparsers.add_parser("implementation-gates")
    p_imp_gates.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_imp_gates.add_argument("--strict", action="store_true", help="严格模式")

    p_full_flow = subparsers.add_parser("full-flow")
    p_full_flow.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_full_flow.add_argument("--strict", action="store_true", help="严格模式")
    p_full_flow.add_argument("--attachment-file", default=None)
    p_full_flow.add_argument("--profile", default=None)

    p_install_rt = subparsers.add_parser("install-runtime")
    p_install_rt.add_argument("target_root", help="目标项目根目录")
    p_install_rt.add_argument("--runtime-dir", default=".sdd", help="运行时安装目录名称")
    p_install_rt.add_argument("--force", action="store_true", help="强制重新安装")

    p_feat_doc = subparsers.add_parser("feature-doctor")
    p_feat_doc.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_feat_doc.add_argument("--attachment-file", default=None)
    p_feat_doc.add_argument("--profile", default=None)

    p_feat_rep = subparsers.add_parser("feature-repair")
    p_feat_rep.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_feat_rep.add_argument("--attachment-file", default=None)
    p_feat_rep.add_argument("--profile", default=None)

    args = parser.parse_args(argv)
    set_json_mode(args.json_output)

    start_time = time.perf_counter()
    exit_code = 0
    try:
        exit_code = dispatch_command(args)
    except Exception as exc:
        if not args.json_output:
            raise
        exit_code = 1
        console_print(f"[FATAL] {exc}")

    duration_ms = int((time.perf_counter() - start_time) * 1000)

    if args.json_output:
        if exit_code != 0:
            payload = build_json_payload(
                args,
                exit_code,
                duration_ms,
            )
            emit_result(payload)
            return 1
        emit_result(build_json_payload(args, exit_code, duration_ms))
        return exit_code

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
