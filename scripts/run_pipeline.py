#!/usr/bin/env python3
"""
run_pipeline.py

试点最小入口：
- init-feature：初始化 specs/<feature>/ 目录和基础文件
- bootstrap：生成 greenfield bootstrap 产物
- greenfield-init：bootstrap 的别名
- scaffold：bootstrap 的别名
- verify：执行 feature-brief 校验
- generate-design：通过 sdd-generation skill 生成 design-v{N}.md 与 design-pack
- init-design：初始化下一版 design-v{N}.md
- check-design：执行 design 最小结构校验
- init-design-pack：按 capability_tags 初始化 design-pack
- check-design-pack：执行 design-pack 最小校验
- gate1：执行设计结构与 design-pack 完整性校验
- gate2：执行真实性 / 结构约束校验
- gate3：执行架构语义审计
- init-approval：为高风险设计生成审批草稿
- check-approval：校验高风险审批文件
- update-design-index：写入设计态索引
- generate-task-slices：根据 feature-brief 与验收矩阵生成 Task Slice 草稿
- gate4：生成测试骨架
- gate5：执行覆盖验证
- release-gate：执行上线前治理检查
- pre-release-check：release-gate 的别名
- go-live-check：release-gate 的别名
- check-arch-standards-sync：校验 docs 与 MCP 架构规范副本同步
- cancel-design：将当前设计意图标记为 CANCELLED
- archive-design：将非活跃设计意图迁移到归档文件
- sync-baseline：Gate 5 通过后同步 Baseline
- refresh-module-map：生成 baseline 类快照
- refresh-schema-context：生成 baseline 表结构快照，支持 polyquery MCP
- refresh-baseline-governance：生成 baseline 治理文档
- attach-project：保存附着目标项目配置
- show-attachment：查看附着目标项目配置
- onboard-project：一键完成 attach + refresh-baseline + project-console-cycle
- bootstrap-attached-project：onboard-project 的别名
- refresh-baseline：顺序生成 baseline 事实快照
- validate-reports：校验 reports/v{N} 结构
- validate-all-reports：校验所有已有 reports 的正式 feature
- prepare-design-cycle：顺序执行 verify -> generate-design -> init-approval
- design-cycle：顺序执行设计轮次准备 + 设计阶段门禁
- build-approval-summary：生成待审批摘要
- approved-implementation-cycle：顺序执行 check-approval -> implementation-gates
- continue-flow：根据当前状态自动推荐并执行下一阶段入口
- flow-status：生成当前 feature 的主流程状态看板
- feature-cycle：顺序执行单 feature 状态刷新 -> 自动推进下一步 -> 再次刷新状态
- flow-overview：生成项目级主流程状态总览
- project-next：生成项目级下一步推荐
- project-console：生成项目级主流程控制台产物
- refresh-project-state：刷新所有正式 feature 的 flow-status
- project-console-cycle：顺序刷新项目状态并生成项目级控制台产物
- continue-project-flow：自动推进当前最值得继续的 feature
- project-cycle：顺序执行项目状态刷新 -> 自动推进一个 feature -> 再次刷新项目状态
- upgrade-design-tests：升级已有设计验证测试为可执行形态
- design-gates：顺序执行设计阶段全部门禁
- implementation-gates：顺序执行实现阶段全部门禁
- full-flow：顺序执行从 verify 到 baseline 同步的主流程
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
from application.pipeline_execution import build_subprocess_env, run_captured_command, run_external_command as app_run_external_command, run_steps
from application.project_runtime import (
    detect_next_flow_step as app_detect_next_flow_step,
    run_continue_flow as app_run_continue_flow,
    run_continue_project_flow as app_run_continue_project_flow,
    run_feature_cycle as app_run_feature_cycle,
    run_project_cycle as app_run_project_cycle,
)
from application.preflight import assert_feature_prerequisites, assert_feature_within_attachment, missing_feature_prerequisites
from attached_project import DEFAULT_ATTACHMENT_PATH, load_attachment_config
from concurrency import atomic_write_text, feature_lock
from infrastructure.baseline_paths import get_active_baseline_dir
from domain.pipeline import PipelineRunContext
from application.flow_state import inspect_feature_state
from ops_log import append_project_op
from polyquery_adapter import DEFAULT_CONFIG_PATH as DEFAULT_POLYQUERY_CONFIG_PATH
from project_artifact_paths import get_active_project_artifacts_dir
from application.pipeline_result import build_result, emit_result
from pipeline_orchestration import append_post_flow_steps, build_design_gate_steps, build_feature_cycle_steps, build_implementation_gate_steps, build_refresh_baseline_steps
from project_flow_runner import capture_project_cycle_candidates, dispatch_feature_next_command, load_project_next_candidate, project_next_json_path, run_project_console_refresh_steps
from install_sdd_runtime import install_runtime as install_local_sdd_runtime
from versioning import detect_latest_design_path, get_primary_design_root, reports_dir_for_design, resolve_feature_dir


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
        for directory in [feature_dir, design_pack_dir, tasks_dir, reports_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        feature_brief = feature_dir / "feature-brief.md"
        if not feature_brief.exists():
            template = DOC_TEMPLATES / "Feature-Brief-模板.md"
            if template.exists():
                atomic_write_text(feature_brief, template.read_text(encoding="utf-8"), encoding="utf-8")
            else:
                atomic_write_text(feature_brief, "# Feature Brief\n", encoding="utf-8")

        task_slice = tasks_dir / "slice-001-biz.md"
        if not task_slice.exists():
            template = DOC_TEMPLATES / "Task-Slice-模板.md"
            if template.exists():
                atomic_write_text(task_slice, template.read_text(encoding="utf-8"), encoding="utf-8")
            else:
                atomic_write_text(task_slice, "# Task Slice\n", encoding="utf-8")

    console_print(f"[OK] 已初始化试点目录: {feature_dir}")
    console_print(f"  - {feature_brief}")
    console_print(f"  - {task_slice}")
    console_print(f"  - {reports_dir}")
    return 0


def generate_feature_brief(
    source_file: str,
    feature_name: str,
    force: bool = False,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    feature_dir = resolve_feature_dir(
        feature_name,
        attachment_path=Path(attachment_file) if attachment_file else DEFAULT_ATTACHMENT_PATH,
        profile=profile,
    )
    feature_dir.mkdir(parents=True, exist_ok=True)
    structured_prd_path = feature_dir / "structured-prd.json"
    feature_brief_path = feature_dir / "feature-brief.md"
    skill_script = ROOT / "skills" / "requirement-analyzer" / "run.py"

    if skill_script.exists():
        cmd = [
            sys.executable,
            str(skill_script),
            source_file,
            str(structured_prd_path),
            "--feature-brief-out",
            str(feature_brief_path),
            "--feature-name",
            feature_dir.name,
        ]
        if force:
            cmd.append("--force")

        result_code = run_external_command(cmd)
        if result_code == 0:
            return 0
        if result_code == 2:
            return 2
        console_print("[WARN] requirement-analyzer 运行失败，回退到 legacy generate_feature_brief.py")

    script = ROOT / "scripts" / "generate_feature_brief.py"
    cmd = [sys.executable, str(script), source_file, feature_name]
    if force:
        cmd.append("--force")
    return run_external_command(cmd)


def verify(feature_brief_path: str) -> int:
    script = ROOT / "scripts" / "check_feature_brief.py"
    return run_external_command([sys.executable, str(script), feature_brief_path])


def bootstrap(feature_dir: str, force: bool = False) -> int:
    script = ROOT / "scripts" / "bootstrap_feature.py"
    cmd = [sys.executable, str(script), feature_dir]
    if force:
        cmd.append("--force")
    return run_external_command(cmd)


def init_design(feature_dir: str) -> int:
    script = ROOT / "scripts" / "init_design.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def generate_design(feature_dir: str, feedback: str | None = None, force: bool = False, resume: bool = False) -> int:
    feature_dir_path = resolve_feature_dir(feature_dir)
    previous_design_path = detect_latest_design_path(feature_dir_path)
    if resume:
        design_path = previous_design_path
        if not design_path.exists():
            console_print(f"[ERROR] --resume 需要已存在的设计文档: {design_path}")
            return 1
    else:
        code = init_design(str(feature_dir_path))
        if code != 0:
            return code
        design_path = detect_latest_design_path(feature_dir_path)
    skill_script = ROOT / "skills" / "sdd-generation" / "run.py"
    if not skill_script.exists():
        console_print("[WARN] 缺少 sdd-generation skill，回退到 init_design_pack")
        return init_design_pack(str(feature_dir_path / "feature-brief.md"))

    feedback_path = feedback
    if not feedback_path:
        if resume:
            current_report = reports_dir_for_design(feature_dir_path, design_path) / "gate-report.json"
            if current_report.exists():
                feedback_path = str(current_report)
        elif previous_design_path.exists() and previous_design_path != design_path:
            previous_report = reports_dir_for_design(feature_dir_path, previous_design_path) / "gate-report.json"
            if previous_report.exists():
                feedback_path = str(previous_report)

    cmd = [
        sys.executable,
        str(skill_script),
        "--workspace",
        str(feature_dir_path),
        "--output",
        str(design_path),
    ]
    if feedback_path:
        cmd.extend(["--feedback", feedback_path])
    if resume:
        cmd.append("--resume")
    if force or not resume:
        cmd.append("--force")
    return run_external_command(cmd)


def check_design(design_file: str) -> int:
    script = ROOT / "scripts" / "check_design_structure.py"
    return run_external_command([sys.executable, str(script), design_file])


def init_design_pack(feature_brief_path: str) -> int:
    script = ROOT / "scripts" / "init_design_pack.py"
    return run_external_command([sys.executable, str(script), feature_brief_path])


def check_design_pack(feature_brief_path: str) -> int:
    script = ROOT / "scripts" / "check_design_pack.py"
    return run_external_command([sys.executable, str(script), feature_brief_path])


def gate1(feature_dir: str) -> int:
    attachment = load_attachment_config(DEFAULT_ATTACHMENT_PATH) if DEFAULT_ATTACHMENT_PATH.exists() else None
    assert_feature_within_attachment(resolve_feature_dir(feature_dir), attachment)
    _context = build_pipeline_run_context(command="gate1", feature_dir=feature_dir)
    script = ROOT / "scripts" / "gate1.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def gate2(feature_dir: str, strict: bool = False) -> int:
    attachment = load_attachment_config(DEFAULT_ATTACHMENT_PATH) if DEFAULT_ATTACHMENT_PATH.exists() else None
    assert_feature_within_attachment(resolve_feature_dir(feature_dir), attachment)
    _context = build_pipeline_run_context(command="gate2", feature_dir=feature_dir, strict=strict)
    script = ROOT / "scripts" / "check_design_truthfulness.py"
    cmd = [sys.executable, str(script), feature_dir]
    if strict:
        cmd.append("--strict")
    return run_external_command(cmd)


def gate3(feature_dir: str) -> int:
    attachment = load_attachment_config(DEFAULT_ATTACHMENT_PATH) if DEFAULT_ATTACHMENT_PATH.exists() else None
    assert_feature_within_attachment(resolve_feature_dir(feature_dir), attachment)
    _context = build_pipeline_run_context(command="gate3", feature_dir=feature_dir)
    script = ROOT / "scripts" / "check_arch_semantics.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def init_approval(feature_dir: str) -> int:
    script = ROOT / "scripts" / "init_approval.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def check_approval(feature_dir: str) -> int:
    script = ROOT / "scripts" / "check_approval.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def approve_design(
    feature_dir: str,
    approved_by: str,
    comments: str = "",
    status: str = "APPROVED",
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    script = ROOT / "scripts" / "approve_design.py"
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


def update_design_index(feature_dir: str) -> int:
    script = ROOT / "scripts" / "update_index_design.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def generate_task_slices(
    feature_dir: str,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    script = ROOT / "scripts" / "generate_task_slices.py"
    cmd = [sys.executable, str(script), feature_dir]
    if attachment_file:
        cmd.extend(["--attachment-file", attachment_file])
    if profile:
        cmd.extend(["--profile", profile])
    return run_external_command(cmd)


def gate4(feature_dir: str) -> int:
    script = ROOT / "scripts" / "generate_test_skeleton.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def gate5(feature_dir: str, require_attached_execution: bool = False, strict: bool = False) -> int:
    attachment = load_attachment_config(DEFAULT_ATTACHMENT_PATH) if DEFAULT_ATTACHMENT_PATH.exists() else None
    assert_feature_within_attachment(resolve_feature_dir(feature_dir), attachment)
    _context = build_pipeline_run_context(command="gate5", feature_dir=feature_dir, strict=strict)
    script = ROOT / "scripts" / "check_design_test_coverage.py"
    cmd = [sys.executable, str(script), feature_dir]
    if require_attached_execution:
        cmd.append("--require-attached-execution")
    if strict:
        cmd.append("--strict")
    return run_external_command(cmd)


def release_gate(feature_dir: str, strict: bool = False) -> int:
    _context = build_pipeline_run_context(command="release-gate", feature_dir=feature_dir, strict=strict)
    script = ROOT / "scripts" / "release_gate.py"
    cmd = [sys.executable, str(script), feature_dir]
    if strict:
        cmd.append("--strict")
    return run_external_command(cmd)


def check_arch_standards_sync() -> int:
    script = ROOT / "scripts" / "check_arch_standards_sync.py"
    return run_external_command([sys.executable, str(script)])


def cancel_design(feature_dir: str, reason: str = "") -> int:
    script = ROOT / "scripts" / "design_index_lifecycle.py"
    cmd = [sys.executable, str(script), "cancel", feature_dir]
    if reason:
        cmd.extend(["--reason", reason])
    return run_external_command(cmd)


def archive_design(feature_name: str | None = None, intent_id: str | None = None, statuses: list[str] | None = None, reason: str = "") -> int:
    script = ROOT / "scripts" / "design_index_lifecycle.py"
    cmd = [sys.executable, str(script), "archive"]
    if feature_name:
        cmd.extend(["--feature-name", feature_name])
    if intent_id:
        cmd.extend(["--intent-id", intent_id])
    for status in statuses or []:
        cmd.extend(["--status", status])
    if reason:
        cmd.extend(["--reason", reason])
    return run_external_command(cmd)


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
) -> int:
    script = ROOT / "scripts" / "attach_target_project.py"
    cmd = [sys.executable, str(script)]
    if list_profiles:
        cmd.append("--list-profiles")
    elif activate_profile:
        cmd.extend(["--activate-profile", activate_profile])
    if show:
        cmd.append("--show")
    elif clear:
        cmd.append("--clear")
    else:
        if project_root:
            cmd.extend(["--project-root", project_root])
        if name:
            cmd.extend(["--name", name])
        if components_file:
            cmd.extend(["--components-file", components_file])
        for design_root in design_roots or []:
            cmd.extend(["--design-root", design_root])
        for schema_root in schema_roots or []:
            cmd.extend(["--schema-root", schema_root])
    if profile:
        cmd.extend(["--profile", profile])
    if project_id:
        cmd.extend(["--project-id", project_id])
    return run_external_command(cmd)


def onboard_project(
    project_root: str | None = None,
    *,
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
    if components_file:
        cmd.extend(["--components-file", components_file])
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

    feature_brief = str(Path(feature_dir) / "feature-brief.md")
    resume_design = detect_latest_design_path(
        Path(
            resolve_feature_dir(
                feature_dir,
                attachment_path=Path(attachment_file) if attachment_file else DEFAULT_ATTACHMENT_PATH,
                profile=profile,
            )
        )
    ).exists()
    return run_steps(
        [
            ("verify", lambda: verify(feature_brief)),
            ("generate-design", lambda: generate_design(feature_dir, force=False, resume=resume_design)),
            ("init-approval", lambda: init_approval(feature_dir)),
        ],
        console_print=console_print,
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
    feature_brief = str(Path(feature_dir) / "feature-brief.md")
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
            getattr(args, "attachment_file", None),
            getattr(args, "profile", None),
        ),
        "pre-release-check": lambda args: release_gate(
            args.feature_dir,
            args.strict,
            getattr(args, "attachment_file", None),
            getattr(args, "profile", None),
        ),
        "go-live-check": lambda args: release_gate(
            args.feature_dir,
            args.strict,
            getattr(args, "attachment_file", None),
            getattr(args, "profile", None),
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
            getattr(args, "attachment_file", None),
            getattr(args, "profile", None),
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

    feature_brief = feature_path / "feature-brief.md"
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

    p_generate_brief = subparsers.add_parser("generate-feature-brief")
    p_generate_brief.add_argument("source_file", help="PRD/需求文本文件路径")
    p_generate_brief.add_argument("feature_name", help="feature 名称或 specs/<feature> 路径")
    p_generate_brief.add_argument("--force", action="store_true", help="允许覆盖已存在的 feature-brief.md")
    p_generate_brief.add_argument("--attachment-file", default=None, help="attachment config path")
    p_generate_brief.add_argument("--profile", default=None, help="attachment profile name")

    p_init = subparsers.add_parser("init-feature")
    p_init.add_argument("feature_name", help="试点 feature 名称，如 order-create")
    p_init.add_argument("--attachment-file", default=None, help="attachment config path")
    p_init.add_argument("--profile", default=None, help="attachment profile name")

    p_bootstrap = subparsers.add_parser("bootstrap")
    p_bootstrap.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_bootstrap.add_argument("--force", action="store_true", help="允许覆盖已存在的 bootstrap 产物")

    p_greenfield_init = subparsers.add_parser("greenfield-init")
    p_greenfield_init.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_greenfield_init.add_argument("--force", action="store_true", help="允许覆盖已存在的 bootstrap 产物")

    p_scaffold = subparsers.add_parser("scaffold")
    p_scaffold.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_scaffold.add_argument("--force", action="store_true", help="允许覆盖已存在的 bootstrap 产物")

    p_verify = subparsers.add_parser("verify")
    p_verify.add_argument("feature_brief", help="feature-brief.md 文件路径")

    p_init_design = subparsers.add_parser("init-design")
    p_init_design.add_argument("feature_dir", help="specs/<feature> 目录路径")

    p_generate_design = subparsers.add_parser("generate-design")
    p_generate_design.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_generate_design.add_argument("--feedback", default=None, help="上一轮 gate-report.json 路径")
    p_generate_design.add_argument("--force", action="store_true", help="允许覆盖当前设计版本与 design-pack")
    p_generate_design.add_argument("--resume", action="store_true", help="基于当前最新设计版本恢复执行")

    p_check_design = subparsers.add_parser("check-design")
    p_check_design.add_argument("design_file", help="design-vN.md 文件路径")

    p_init_dp = subparsers.add_parser("init-design-pack")
    p_init_dp.add_argument("feature_brief", help="feature-brief.md 文件路径")

    p_check_dp = subparsers.add_parser("check-design-pack")
    p_check_dp.add_argument("feature_brief", help="feature-brief.md 文件路径")

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
    p_approve_design.add_argument("feature_dir", help="specs/<feature> feature directory")
    p_approve_design.add_argument("--approved-by", required=True, help="approver name")
    p_approve_design.add_argument("--comments", default="", help="approval comments")
    p_approve_design.add_argument("--attachment-file", default=None, help="attachment config path")
    p_approve_design.add_argument("--profile", default=None, help="attachment profile name")
    p_approve_design.add_argument(
        "--status",
        choices=["APPROVED", "REJECTED", "PENDING"],
        default="APPROVED",
        help="approval status, defaults to APPROVED",
    )

    p_check_approval = subparsers.add_parser("check-approval")
    p_check_approval.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_check_approval.add_argument("--attachment-file", default=None, help="attachment config path")
    p_check_approval.add_argument("--profile", default=None, help="attachment profile name")

    p_update_index = subparsers.add_parser("update-design-index")
    p_update_index.add_argument("feature_dir", help="specs/<feature> 目录路径")

    p_generate_slices = subparsers.add_parser("generate-task-slices")
    p_generate_slices.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_generate_slices.add_argument("--attachment-file", default=None, help="attachment config path")
    p_generate_slices.add_argument("--profile", default=None, help="attachment profile name")

    p_gate4 = subparsers.add_parser("gate4")
    p_gate4.add_argument("feature_dir", help="specs/<feature> 目录路径")

    p_gate5 = subparsers.add_parser("gate5")
    p_gate5.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_gate5.add_argument("--require-attached-execution", action="store_true", help="要求附着项目 verification_commands 成功执行")
    p_gate5.add_argument("--strict", action="store_true", help="严格模式")
    p_gate5.add_argument("--attachment-file", default=None, help="attachment config path")
    p_gate5.add_argument("--profile", default=None, help="attachment profile name")

    p_release_gate = subparsers.add_parser("release-gate")
    p_release_gate.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_release_gate.add_argument("--strict", action="store_true", help="严格模式")
    p_release_gate.add_argument("--attachment-file", default=None, help="attachment config path")
    p_release_gate.add_argument("--profile", default=None, help="attachment profile name")

    p_pre_release = subparsers.add_parser("pre-release-check")
    p_pre_release.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_pre_release.add_argument("--strict", action="store_true", help="严格模式")

    p_go_live = subparsers.add_parser("go-live-check")
    p_go_live.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_go_live.add_argument("--strict", action="store_true", help="严格模式")

    subparsers.add_parser("check-arch-standards-sync")

    p_cancel_design = subparsers.add_parser("cancel-design")
    p_cancel_design.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_cancel_design.add_argument("--reason", default="", help="取消原因")

    p_archive_design = subparsers.add_parser("archive-design")
    p_archive_design.add_argument("--feature-name", default=None, help="按 feature 归档")
    p_archive_design.add_argument("--intent-id", default=None, help="按 intent_id 归档")
    p_archive_design.add_argument(
        "--status",
        action="append",
        choices=["ACTIVE", "SUPERSEDED", "CANCELLED", "IMPLEMENTED"],
        default=None,
        help="仅归档指定状态，可重复传入",
    )
    p_archive_design.add_argument("--reason", default="", help="归档原因")

    p_sync = subparsers.add_parser("sync-baseline")
    p_sync.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_sync.add_argument("--design-version", default=None, help="显式同步 design-vN.md / vN / N")

    p_refresh_module_map = subparsers.add_parser("refresh-module-map")
    p_refresh_module_map.add_argument("--attachment-file", default=None, help="attachment config path")
    p_refresh_module_map.add_argument("--profile", default=None, help="attachment profile name")
    p_attach = subparsers.add_parser("attach-project")
    p_attach.add_argument("--project-root", default=None, help="目标项目根目录")
    p_attach.add_argument("--name", default=None, help="附着项目显示名称")
    p_attach.add_argument("--profile", default=None, help="多项目 profile 名称")
    p_attach.add_argument("--project-id", default=None, help="显式 project_id")
    p_attach.add_argument("--design-root", action="append", default=None, help="显式 design 根目录，可重复传入")
    p_attach.add_argument("--schema-root", action="append", default=None, help="显式 schema 根目录，可重复传入")
    p_attach.add_argument("--components-file", default=None, help="components[] 或完整 attached-project payload JSON")
    p_attach.add_argument("--list-profiles", action="store_true", help="列出 attachment profiles")
    p_attach.add_argument("--activate-profile", default=None, help="切换 active attachment profile")
    p_attach.add_argument("--clear", action="store_true", help="清空附着配置")
    p_attach.add_argument("--attachment-file", default=None, help="attachment config path")
    p_show_attachment = subparsers.add_parser("show-attachment")
    p_show_attachment.add_argument("--profile", default=None, help="查看指定 profile 的 attachment 配置")
    p_onboard = subparsers.add_parser("onboard-project")
    p_onboard.add_argument("--project-root", default=None, help="目标项目根目录")
    p_onboard.add_argument("--name", default=None, help="附着项目显示名称")
    p_onboard.add_argument("--profile", default=None, help="多项目 profile 名称")
    p_onboard.add_argument("--project-id", default=None, help="显式 project_id")
    p_onboard.add_argument("--design-root", action="append", default=None, help="显式 design 根目录，可重复传入")
    p_onboard.add_argument("--schema-root", action="append", default=None, help="显式 schema 根目录，可重复传入")
    p_onboard.add_argument("--components-file", default=None, help="components[] 或完整 attached-project payload JSON")
    p_onboard.add_argument("--attachment-file", default=None, help="attachment config path")
    p_bootstrap_attached = subparsers.add_parser("bootstrap-attached-project")
    p_bootstrap_attached.add_argument("--project-root", default=None, help="目标项目根目录")
    p_bootstrap_attached.add_argument("--name", default=None, help="附着项目显示名称")
    p_bootstrap_attached.add_argument("--profile", default=None, help="多项目 profile 名称")
    p_bootstrap_attached.add_argument("--project-id", default=None, help="显式 project_id")
    p_bootstrap_attached.add_argument("--design-root", action="append", default=None, help="显式 design 根目录，可重复传入")
    p_bootstrap_attached.add_argument("--schema-root", action="append", default=None, help="显式 schema 根目录，可重复传入")
    p_bootstrap_attached.add_argument("--components-file", default=None, help="components[] 或完整 attached-project payload JSON")
    p_refresh_schema = subparsers.add_parser("refresh-schema-context")
    p_refresh_schema.add_argument("--attachment-file", default=None, help="attachment config path")
    p_refresh_schema.add_argument("--profile", default=None, help="attachment profile name")
    p_refresh_schema.add_argument("--from-polyquery", action="store_true", help="优先从 polyquery MCP 生成 schema-context")
    p_refresh_schema.add_argument("--polyquery-config", default=None, help="polyquery 配置文件路径")
    p_refresh_schema.add_argument("--polyquery-snapshot", default=None, help="polyquery snapshot 文件路径")
    p_refresh_schema.add_argument("--auto-discover", default=None, help="指定 specs/<feature> 目录，自动发现需要沉淀的表")
    p_refresh_schema.add_argument(
        "--polyquery-fallback",
        choices=["local", "fail"],
        default="local",
        help="polyquery 失败时是否回退本地快照",
    )
    subparsers.add_parser("refresh-baseline-governance")
    p_refresh_baseline = subparsers.add_parser("refresh-baseline")
    p_refresh_baseline.add_argument("--attachment-file", default=None, help="attachment config path")
    p_refresh_baseline.add_argument("--profile", default=None, help="attachment profile name")
    p_refresh_baseline.add_argument("--feature-dir", default=None, help="optional feature dir used for strict auto-discovery")
    p_refresh_baseline.add_argument("--strict", action="store_true", help="strict mode")
    p_refresh_project = subparsers.add_parser("refresh-project-state")
    p_refresh_project.add_argument("--attachment-file", default=None, help="attachment config path")
    p_refresh_project.add_argument("--profile", default=None, help="attachment profile name")
    p_refresh_project.add_argument("--feature", default=None, help="仅刷新指定 feature 目录名")

    p_validate_reports = subparsers.add_parser("validate-reports")
    p_validate_reports.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_validate_reports.add_argument("--attachment-file", default=None, help="attachment config path")
    p_validate_reports.add_argument("--profile", default=None, help="attachment profile name")
    p_validate_reports.add_argument(
        "--stage",
        choices=["design", "implementation", "all"],
        default="all",
        help="仅校验设计阶段报告、实现阶段报告，或全部",
    )

    p_validate_all_reports = subparsers.add_parser("validate-all-reports")
    p_validate_all_reports.add_argument(
        "--stage",
        choices=["design", "implementation", "all"],
        default="all",
        help="仅校验设计阶段报告、实现阶段报告，或全部",
    )
    p_validate_all_reports.add_argument("--attachment-file", default=None, help="attachment config path")
    p_validate_all_reports.add_argument("--profile", default=None, help="attachment profile name")
    p_validate_all_reports.add_argument("--require-verify", action="store_true", help="要求所有正式 feature 都必须已有 verify-report.json")

    p_build_summary = subparsers.add_parser("build-approval-summary")
    p_build_summary.add_argument("feature_dir", help="specs/<feature> 目录路径")

    p_approved_impl = subparsers.add_parser("approved-implementation-cycle")
    p_approved_impl.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_approved_impl.add_argument("--attachment-file", default=None, help="attachment config path")
    p_approved_impl.add_argument("--profile", default=None, help="attachment profile name")
    p_approved_impl.add_argument("--strict", action="store_true", help="严格模式")

    p_continue = subparsers.add_parser("continue-flow")
    p_continue.add_argument("feature_dir", help="specs/<feature> 目录路径")

    p_flow_status = subparsers.add_parser("flow-status")
    p_flow_status.add_argument("--attachment-file", default=None, help="attachment config path")
    p_flow_status.add_argument("--profile", default=None, help="attachment profile name")
    p_flow_status.add_argument("feature_dir", help="specs/<feature> 目录路径")

    p_feature_cycle = subparsers.add_parser("feature-cycle")
    p_feature_cycle.add_argument("feature_dir", help="specs/<feature> 目录路径")

    p_flow_overview = subparsers.add_parser("flow-overview")
    p_flow_overview.add_argument("--attachment-file", default=None, help="attachment config path")
    p_flow_overview.add_argument("--profile", default=None, help="attachment profile name")
    p_project_next = subparsers.add_parser("project-next")
    p_project_next.add_argument("--attachment-file", default=None, help="attachment config path")
    p_project_next.add_argument("--profile", default=None, help="attachment profile name")
    p_project_console = subparsers.add_parser("project-console")
    p_project_console.add_argument("--attachment-file", default=None, help="attachment config path")
    p_project_console.add_argument("--profile", default=None, help="attachment profile name")
    p_project_console_cycle = subparsers.add_parser("project-console-cycle")
    p_project_console_cycle.add_argument("--attachment-file", default=None, help="attachment config path")
    p_project_console_cycle.add_argument("--profile", default=None, help="attachment profile name")
    p_continue_project_flow = subparsers.add_parser("continue-project-flow")
    p_continue_project_flow.add_argument("--attachment-file", default=None, help="attachment config path")
    p_continue_project_flow.add_argument("--profile", default=None, help="attachment profile name")
    p_project_cycle = subparsers.add_parser("project-cycle")
    p_project_cycle.add_argument("--attachment-file", default=None, help="attachment config path")
    p_project_cycle.add_argument("--profile", default=None, help="attachment profile name")
    subparsers.add_parser("tooling-hygiene")
    subparsers.add_parser("workspace-hygiene")

    p_upgrade_design = subparsers.add_parser("upgrade-design-tests")
    p_upgrade_design.add_argument("--attachment-file", default=None, help="attachment config path")
    p_upgrade_design.add_argument("--profile", default=None, help="attachment profile name")
    p_upgrade_design.add_argument("--feature", default=None, help="仅升级指定 feature_name 对应的测试")

    p_prepare_design = subparsers.add_parser("prepare-design-cycle")
    p_prepare_design.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_prepare_design.add_argument("--attachment-file", default=None, help="attachment config path")
    p_prepare_design.add_argument("--profile", default=None, help="attachment profile name")

    p_design_cycle = subparsers.add_parser("design-cycle")
    p_design_cycle.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_design_cycle.add_argument("--attachment-file", default=None, help="attachment config path")
    p_design_cycle.add_argument("--profile", default=None, help="attachment profile name")
    p_design_cycle.add_argument("--strict", action="store_true", help="严格模式")

    p_design_gates = subparsers.add_parser("design-gates")
    p_design_gates.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_design_gates.add_argument("--attachment-file", default=None, help="attachment config path")
    p_design_gates.add_argument("--profile", default=None, help="attachment profile name")
    p_design_gates.add_argument("--strict", action="store_true", help="严格模式")

    p_impl_gates = subparsers.add_parser("implementation-gates")
    p_impl_gates.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_impl_gates.add_argument("--strict", action="store_true", help="严格模式")

    p_full = subparsers.add_parser("full-flow")
    p_full.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_full.add_argument("--attachment-file", default=None, help="attachment config path")
    p_full.add_argument("--profile", default=None, help="attachment profile name")
    p_full.add_argument("--strict", action="store_true", help="严格模式")

    p_install_runtime = subparsers.add_parser("install-runtime")
    p_install_runtime.add_argument("--target-root", required=True, help="target project root")
    p_install_runtime.add_argument("--runtime-dir", default=".sdd-runtime", help="runtime directory name")
    p_install_runtime.add_argument("--force", action="store_true", help="replace existing runtime directory")

    p_feature_doctor = subparsers.add_parser("feature-doctor")
    p_feature_doctor.add_argument("feature_dir", help="specs/<feature> directory path")
    p_feature_doctor.add_argument("--attachment-file", default=None, help="attachment config path")
    p_feature_doctor.add_argument("--profile", default=None, help="attachment profile name")

    p_feature_repair = subparsers.add_parser("feature-repair")
    p_feature_repair.add_argument("feature_dir", help="specs/<feature> directory path")
    p_feature_repair.add_argument("--attachment-file", default=None, help="attachment config path")
    p_feature_repair.add_argument("--profile", default=None, help="attachment profile name")

    args = parser.parse_args(argv)

    if args.json_output:
        set_json_mode(True)
        reset_execution_trace()
        started_at = time.time()
        try:
            exit_code = dispatch_command(args)
            payload = build_json_payload(args, exit_code, int((time.time() - started_at) * 1000))
        except Exception as exc:
            payload = build_result(
                status="error",
                message=f"{args.cmd} failed with an unexpected exception",
                data={
                    "command": args.cmd,
                    "duration_ms": int((time.time() - started_at) * 1000),
                    "execution_trace": list(EXECUTION_TRACE),
                },
                errors=[f"{type(exc).__name__}: {exc}"],
                artifacts=collect_artifacts_for_command(args),
            )
            emit_result(payload)
            return 1
        emit_result(payload)
        return exit_code

    return dispatch_command(args)


if __name__ == "__main__":
    raise SystemExit(main())
