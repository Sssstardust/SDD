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
from pathlib import Path

from attached_project import DEFAULT_ATTACHMENT_PATH
from concurrency import atomic_write_text, feature_lock
from flow_state import inspect_feature_state
from json_io import read_json
from ops_log import append_project_op
from polyquery_adapter import DEFAULT_CONFIG_PATH as DEFAULT_POLYQUERY_CONFIG_PATH
from project_artifact_paths import get_active_project_artifacts_dir
from pipeline_result import build_result, emit_result
from pipeline_orchestration import append_post_flow_steps, build_design_gate_steps, build_feature_cycle_steps, build_implementation_gate_steps, build_refresh_baseline_steps
from project_flow_runner import capture_project_cycle_candidates, dispatch_feature_next_command, load_project_next_candidate, project_next_json_path, run_project_console_refresh_steps
from versioning import detect_latest_design_path, get_primary_design_root, reports_dir_for_design, resolve_feature_dir


ROOT = Path(__file__).resolve().parent.parent
DOC_TEMPLATES = ROOT / "document" / "template"
JSON_MODE = False
EXECUTION_TRACE: list[dict[str, object]] = []


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
    if JSON_MODE:
        return run_traced_captured_command(command).returncode
    result = subprocess.run(command, check=False, env=build_subprocess_env())
    return result.returncode


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


def init_feature(feature_name: str) -> int:
    feature_dir = get_primary_design_root() / feature_name
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


def generate_feature_brief(source_file: str, feature_name: str, force: bool = False) -> int:
    feature_dir = resolve_feature_dir(feature_name)
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
    script = ROOT / "scripts" / "gate1.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def gate2(feature_dir: str, strict: bool = False) -> int:
    script = ROOT / "scripts" / "check_design_truthfulness.py"
    cmd = [sys.executable, str(script), feature_dir]
    if strict:
        cmd.append("--strict")
    return run_external_command(cmd)


def gate3(feature_dir: str) -> int:
    script = ROOT / "scripts" / "check_arch_semantics.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def init_approval(feature_dir: str) -> int:
    script = ROOT / "scripts" / "init_approval.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def check_approval(feature_dir: str) -> int:
    script = ROOT / "scripts" / "check_approval.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def approve_design(feature_dir: str, approved_by: str, comments: str = "", status: str = "APPROVED") -> int:
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
    return run_external_command(cmd)


def update_design_index(feature_dir: str) -> int:
    script = ROOT / "scripts" / "update_index_design.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def generate_task_slices(feature_dir: str) -> int:
    script = ROOT / "scripts" / "generate_task_slices.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def gate4(feature_dir: str) -> int:
    script = ROOT / "scripts" / "generate_test_skeleton.py"
    return run_external_command([sys.executable, str(script), feature_dir])


def gate5(feature_dir: str, require_attached_execution: bool = False, strict: bool = False) -> int:
    script = ROOT / "scripts" / "check_design_test_coverage.py"
    cmd = [sys.executable, str(script), feature_dir]
    if require_attached_execution:
        cmd.append("--require-attached-execution")
    if strict:
        cmd.append("--strict")
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


def run_steps(steps: list[tuple[str, callable]]) -> int:
    for label, step in steps:
        console_print(f"[RUN] {label}")
        code = step()
        if code != 0:
            console_print(f"[STOP] {label} failed with exit code {code}")
            return code
    return 0


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
        )
    )


def run_prepare_design_cycle(feature_dir: str) -> int:
    feature_brief = str(Path(feature_dir) / "feature-brief.md")
    return run_steps(
        [
            ("verify", lambda: verify(feature_brief)),
            ("generate-design", lambda: generate_design(feature_dir, force=True)),
            ("init-approval", lambda: init_approval(feature_dir)),
        ]
    )


def run_design_cycle(
    feature_dir: str,
    strict: bool = False,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
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
        )
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
        )
    )


def run_approved_implementation_cycle(
    feature_dir: str,
    strict: bool = False,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
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
        )
    )


def detect_next_flow_step(feature_dir: str) -> tuple[str, callable]:
    normalized_feature_dir = resolve_feature_dir(feature_dir)
    state = inspect_feature_state(normalized_feature_dir, prefer_persisted=False)
    next_command = str(state.get("next_command") or "")
    strict = next_command_requires_strict(next_command)
    dispatched = dispatch_feature_next_command(
        next_command=next_command,
        feature_dir=str(normalized_feature_dir),
        strict=strict,
        init_feature=init_feature,
        bootstrap=bootstrap,
        run_design_cycle=run_design_cycle,
        build_approval_summary=build_approval_summary,
        run_approved_implementation_cycle=run_approved_implementation_cycle,
        release_gate=release_gate,
        run_full_flow=run_full_flow,
    )
    if dispatched is None:
        return ("full-flow", lambda: run_full_flow(str(normalized_feature_dir), strict=strict))
    return dispatched


def run_continue_flow(feature_dir: str) -> int:
    label, action = detect_next_flow_step(feature_dir)
    return run_steps(
        [
            (label, action),
            ("flow-status", lambda: refresh_feature_state(feature_dir)),
        ]
    )


def run_feature_cycle(feature_dir: str) -> int:
    return run_steps(
        build_feature_cycle_steps(
            feature_dir=feature_dir,
            continue_action=lambda: run_continue_flow(feature_dir),
            refresh_feature_state=refresh_feature_state,
        )
    )


def run_continue_project_flow(
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    script = ROOT / "scripts" / "build_project_next.py"
    command = [sys.executable, str(script)]
    if attachment_file:
        command.extend(["--attachment-file", attachment_file])
    if profile:
        command.extend(["--profile", profile])
    result = run_traced_captured_command(command)
    if result.returncode != 0:
        if not JSON_MODE:
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr)
        return result.returncode

    project_next_path = project_next_json_path(attachment_file=attachment_file, profile=profile)
    if not project_next_path.exists():
        console_print("[ERROR] project-next.json 未生成")
        return 1

    candidate, payload = load_project_next_candidate(attachment_file=attachment_file, profile=profile)
    if not isinstance(payload, dict):
        console_print("[ERROR] project-next.json 结构非法")
        return 1

    if not isinstance(candidate, dict):
        append_project_op("continue-project-flow", {"result": "no_candidate"})
        console_print("[OK] 当前没有需要自动推进的 feature")
        return 0

    next_command = str(candidate.get("next_command") or "")
    feature_name = str(candidate.get("feature_name") or "")
    feature_dir = str(candidate.get("feature_dir") or "")
    from_stage = str(candidate.get("current_stage") or "")
    reason = str(candidate.get("reason") or "")
    strict = next_command_requires_strict(next_command)
    if not next_command:
        console_print("[ERROR] 候选 feature 缺少 next_command")
        return 1

    console_print(f"[OK] 选择推进 feature: {feature_name}")
    console_print(f"  - command: {next_command}")
    summary = {
        "feature": feature_name,
        "feature_dir": feature_dir,
        "from_stage": from_stage,
        "reason": reason,
        "command": next_command,
    }

    dispatched = dispatch_feature_next_command(
        next_command=next_command,
        feature_dir=feature_dir,
        strict=strict,
        init_feature=init_feature,
        bootstrap=bootstrap,
        run_design_cycle=run_design_cycle,
        build_approval_summary=build_approval_summary,
        run_approved_implementation_cycle=run_approved_implementation_cycle,
        release_gate=release_gate,
        run_full_flow=run_full_flow,
        attachment_file=attachment_file,
        profile=profile,
    )
    if dispatched is None:
        console_print("[ERROR] 无法解析 project-next 推荐命令")
        return 1
    _label, action = dispatched
    code = action()

    after_state = inspect_feature_state(Path(feature_dir), prefer_persisted=False)
    summary["result"] = "ok" if code == 0 else "fail"
    summary["exit_code"] = code
    summary["after_stage"] = after_state.get("current_stage")
    summary["after_reason"] = after_state.get("reason")
    append_project_op("continue-project-flow", summary)
    return code


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
    before = run_project_console_cycle(attachment_file=attachment_file, profile=profile)
    if before != 0:
        append_project_op("project-cycle", {"result": "fail", "failed_step": "project-console-cycle(before)"})
        return before

    before_snapshot = capture_project_cycle_candidates(attachment_file=attachment_file, profile=profile)

    continue_code = run_continue_project_flow(attachment_file=attachment_file, profile=profile)

    after = run_project_console_cycle(attachment_file=attachment_file, profile=profile)
    if after != 0:
        append_project_op("project-cycle", {"result": "fail", "failed_step": "project-console-cycle(after)"})
        return after

    after_snapshot = capture_project_cycle_candidates(attachment_file=attachment_file, profile=profile)

    append_project_op(
        "project-cycle",
        {
            "result": "ok" if continue_code == 0 else "fail",
            "continue_code": continue_code,
            "before_candidate": before_snapshot.get("candidate"),
            "after_candidate": after_snapshot.get("candidate"),
        },
    )
    return continue_code


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
        )
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

    return run_steps(
        build_refresh_baseline_steps(
            refresh_module_map=refresh_module_map,
            refresh_schema_context=refresh_schema_context,
            refresh_baseline_governance=refresh_baseline_governance,
            check_baseline_keys=check_baseline_keys,
            attachment_file=attachment_file,
            profile=profile,
            refresh_strategy=refresh_strategy,
        )
    )


def latest_report_artifact(feature_dir: str, filename: str) -> str | None:
    feature_dir_path = resolve_feature_dir(feature_dir)
    design_path = detect_latest_design_path(feature_dir_path)
    if not design_path.exists():
        return None
    report_path = reports_dir_for_design(feature_dir_path, design_path) / filename
    return str(report_path) if report_path.exists() else None


def collect_artifacts_for_command(args: argparse.Namespace) -> dict[str, object]:
    artifacts: dict[str, object] = {}
    cmd = getattr(args, "cmd", "")
    attachment_file = getattr(args, "attachment_file", None)
    profile = getattr(args, "profile", None)
    resolve_kwargs = {}
    if attachment_file:
        resolve_kwargs["attachment_path"] = Path(attachment_file)
    if profile:
        resolve_kwargs["profile"] = profile
    if cmd == "flow-status":
        flow_status_path = resolve_feature_dir(args.feature_dir, **resolve_kwargs) / "flow-status.json"
        project_state_path = resolve_feature_dir(args.feature_dir, **resolve_kwargs) / "project-state.json"
        if project_state_path.exists():
            artifacts["project_state_path"] = str(project_state_path)
        if flow_status_path.exists():
            artifacts["flow_status_path"] = str(flow_status_path)
    elif cmd == "generate-task-slices":
        task_slices_path = resolve_feature_dir(args.feature_dir, **resolve_kwargs) / "tasks" / "task-slices.generated.json"
        if task_slices_path.exists():
            artifacts["task_slices_path"] = str(task_slices_path)
    elif cmd == "gate5":
        verify_report_path = latest_report_artifact(args.feature_dir, "verify-report.json")
        if verify_report_path:
            artifacts["verify_report_path"] = verify_report_path
    elif cmd in {"release-gate", "pre-release-check", "go-live-check"}:
        release_gate_report_path = latest_report_artifact(args.feature_dir, "release-gate-report.json")
        if release_gate_report_path:
            artifacts["release_gate_report_path"] = release_gate_report_path
    elif cmd in {"project-next", "project-console-cycle", "project-cycle", "continue-project-flow"}:
        artifacts_dir = get_active_project_artifacts_dir(
            attachment_path=Path(attachment_file) if attachment_file else DEFAULT_ATTACHMENT_PATH,
            profile=profile,
            create=True,
        )
        project_next_path = artifacts_dir / "project-next.json"
        project_console_path = artifacts_dir / "project-console.json"
        if project_next_path.exists():
            artifacts["project_next_path"] = str(project_next_path)
        if project_console_path.exists():
            artifacts["project_console_path"] = str(project_console_path)
    return artifacts


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


def dispatch_command(args: argparse.Namespace) -> int:
    if args.cmd == "generate-feature-brief":
        return generate_feature_brief(args.source_file, args.feature_name, args.force)
    if args.cmd == "init-feature":
        return init_feature(args.feature_name)
    if args.cmd in {"bootstrap", "greenfield-init", "scaffold"}:
        return bootstrap(args.feature_dir, args.force)
    if args.cmd == "verify":
        return verify(args.feature_brief)
    if args.cmd == "init-design":
        return init_design(args.feature_dir)
    if args.cmd == "generate-design":
        return generate_design(args.feature_dir, args.feedback, args.force, args.resume)
    if args.cmd == "check-design":
        return check_design(args.design_file)
    if args.cmd == "init-design-pack":
        return init_design_pack(args.feature_brief)
    if args.cmd == "check-design-pack":
        return check_design_pack(args.feature_brief)
    if args.cmd == "gate1":
        return gate1(args.feature_dir)
    if args.cmd == "gate2":
        return gate2(args.feature_dir, args.strict)
    if args.cmd == "gate3":
        return gate3(args.feature_dir)
    if args.cmd == "init-approval":
        return init_approval(args.feature_dir)
    if args.cmd == "approve-design":
        return approve_design(args.feature_dir, args.approved_by, args.comments, args.status)
    if args.cmd == "check-approval":
        return check_approval(args.feature_dir)
    if args.cmd == "update-design-index":
        return update_design_index(args.feature_dir)
    if args.cmd == "generate-task-slices":
        return generate_task_slices(args.feature_dir)
    if args.cmd == "gate4":
        return gate4(args.feature_dir)
    if args.cmd == "gate5":
        return gate5(args.feature_dir, args.require_attached_execution, args.strict)
    if args.cmd in {"release-gate", "pre-release-check", "go-live-check"}:
        return release_gate(args.feature_dir, args.strict)
    if args.cmd == "check-arch-standards-sync":
        return check_arch_standards_sync()
    if args.cmd == "cancel-design":
        return cancel_design(args.feature_dir, args.reason)
    if args.cmd == "archive-design":
        return archive_design(args.feature_name, args.intent_id, args.status, args.reason)
    if args.cmd == "sync-baseline":
        return sync_baseline(args.feature_dir, args.design_version)
    if args.cmd == "refresh-module-map":
        return refresh_module_map(args.attachment_file, args.profile)
    if args.cmd == "attach-project":
        return attach_project(
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
        )
    if args.cmd == "show-attachment":
        return attach_project(show=True, profile=args.profile)
    if args.cmd in {"onboard-project", "bootstrap-attached-project"}:
        return onboard_project(
            args.project_root,
            name=args.name,
            design_roots=args.design_root,
            schema_roots=args.schema_root,
            components_file=args.components_file,
            profile=args.profile,
            project_id=args.project_id,
        )
    if args.cmd == "refresh-schema-context":
        return refresh_schema_context(
            from_polyquery=args.from_polyquery,
            polyquery_config=args.polyquery_config,
            polyquery_snapshot=args.polyquery_snapshot,
            auto_discover=args.auto_discover,
            polyquery_fallback=args.polyquery_fallback,
            attachment_file=args.attachment_file,
            profile=args.profile,
        )
    if args.cmd == "refresh-baseline-governance":
        return refresh_baseline_governance()
    if args.cmd == "refresh-baseline":
        return run_refresh_baseline(
            strict=getattr(args, "strict", False),
            feature_dir=getattr(args, "feature_dir", None),
            attachment_file=args.attachment_file,
            profile=args.profile,
        )
    if args.cmd == "refresh-project-state":
        return refresh_project_state(args.feature, args.attachment_file, args.profile)
    if args.cmd == "validate-reports":
        return validate_reports(args.feature_dir, args.stage)
    if args.cmd == "validate-all-reports":
        return validate_all_reports(args.stage, args.require_verify, args.attachment_file, args.profile)
    if args.cmd == "build-approval-summary":
        return build_approval_summary(args.feature_dir)
    if args.cmd == "approved-implementation-cycle":
        return run_approved_implementation_cycle(
            args.feature_dir,
            args.strict,
            getattr(args, "attachment_file", None),
            getattr(args, "profile", None),
        )
    if args.cmd == "continue-flow":
        return run_continue_flow(args.feature_dir)
    if args.cmd == "flow-status":
        return build_flow_status(args.feature_dir, args.attachment_file, args.profile)
    if args.cmd == "feature-cycle":
        return run_feature_cycle(args.feature_dir)
    if args.cmd == "flow-overview":
        return build_flow_overview(args.attachment_file, args.profile)
    if args.cmd == "project-next":
        return build_project_next(args.attachment_file, args.profile)
    if args.cmd == "project-console":
        return build_project_console(args.attachment_file, args.profile)
    if args.cmd == "project-console-cycle":
        return run_project_console_cycle(args.attachment_file, args.profile)
    if args.cmd == "continue-project-flow":
        return run_continue_project_flow(args.attachment_file, args.profile)
    if args.cmd == "project-cycle":
        return run_project_cycle(args.attachment_file, args.profile)
    if args.cmd == "tooling-hygiene":
        return build_tooling_hygiene()
    if args.cmd == "workspace-hygiene":
        return build_workspace_hygiene()
    if args.cmd == "upgrade-design-tests":
        return upgrade_design_tests(args.feature, args.attachment_file, args.profile)
    if args.cmd == "prepare-design-cycle":
        return run_prepare_design_cycle(args.feature_dir)
    if args.cmd == "design-cycle":
        return run_design_cycle(args.feature_dir, args.strict, args.attachment_file, args.profile)
    if args.cmd == "design-gates":
        return run_design_gates(args.feature_dir, args.strict, args.attachment_file, args.profile)
    if args.cmd == "implementation-gates":
        return run_implementation_gates(args.feature_dir, args.strict)
    if args.cmd == "full-flow":
        return run_full_flow(args.feature_dir, args.strict, args.attachment_file, args.profile)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", dest="json_output", action="store_true", help="emit structured JSON result")
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    p_generate_brief = subparsers.add_parser("generate-feature-brief")
    p_generate_brief.add_argument("source_file", help="PRD/需求文本文件路径")
    p_generate_brief.add_argument("feature_name", help="feature 名称或 specs/<feature> 路径")
    p_generate_brief.add_argument("--force", action="store_true", help="允许覆盖已存在的 feature-brief.md")

    p_init = subparsers.add_parser("init-feature")
    p_init.add_argument("feature_name", help="试点 feature 名称，如 order-create")

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
    p_approve_design.add_argument(
        "--status",
        choices=["APPROVED", "REJECTED", "PENDING"],
        default="APPROVED",
        help="approval status, defaults to APPROVED",
    )

    p_check_approval = subparsers.add_parser("check-approval")
    p_check_approval.add_argument("feature_dir", help="specs/<feature> 目录路径")

    p_update_index = subparsers.add_parser("update-design-index")
    p_update_index.add_argument("feature_dir", help="specs/<feature> 目录路径")

    p_generate_slices = subparsers.add_parser("generate-task-slices")
    p_generate_slices.add_argument("feature_dir", help="specs/<feature> 目录路径")

    p_gate4 = subparsers.add_parser("gate4")
    p_gate4.add_argument("feature_dir", help="specs/<feature> 目录路径")

    p_gate5 = subparsers.add_parser("gate5")
    p_gate5.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_gate5.add_argument("--require-attached-execution", action="store_true", help="要求附着项目 verification_commands 成功执行")
    p_gate5.add_argument("--strict", action="store_true", help="严格模式")

    p_release_gate = subparsers.add_parser("release-gate")
    p_release_gate.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_release_gate.add_argument("--strict", action="store_true", help="严格模式")

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
