#!/usr/bin/env python3
"""
Application-layer feature/project flow orchestration.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from application.pipeline_execution import run_steps


def detect_next_flow_step(
    feature_dir: str,
    *,
    inspect_feature_state: Callable[..., dict[str, object]],
    resolve_feature_dir: Callable[[str], Path],
    next_command_requires_strict: Callable[[str], bool],
    dispatch_feature_next_command: Callable[..., tuple[str, Callable[[], int]] | None],
    init_feature: Callable[[str], int],
    bootstrap: Callable[[str], int],
    run_design_cycle: Callable[..., int],
    build_approval_summary: Callable[[str], int],
    run_approved_implementation_cycle: Callable[..., int],
    release_gate: Callable[[str, bool], int],
    run_full_flow: Callable[..., int],
) -> tuple[str, Callable[[], int]]:
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


def run_continue_flow(
    feature_dir: str,
    *,
    detect_next_flow_step_fn: Callable[[str], tuple[str, Callable[[], int]]],
    refresh_feature_state: Callable[[str], int],
    console_print: Callable[[str], None],
) -> int:
    label, action = detect_next_flow_step_fn(feature_dir)
    return run_steps(
        [
            (label, action),
            ("flow-status", lambda: refresh_feature_state(feature_dir)),
        ],
        console_print=console_print,
    )


def run_feature_cycle(
    feature_dir: str,
    *,
    build_feature_cycle_steps: Callable[..., list[tuple[str, Callable[[], int]]]],
    run_continue_flow_fn: Callable[[str], int],
    refresh_feature_state: Callable[..., int],
    console_print: Callable[[str], None],
) -> int:
    return run_steps(
        build_feature_cycle_steps(
            feature_dir=feature_dir,
            continue_action=lambda: run_continue_flow_fn(feature_dir),
            refresh_feature_state=refresh_feature_state,
        ),
        console_print=console_print,
    )


def run_continue_project_flow(
    *,
    attachment_file: str | None,
    profile: str | None,
    root: Path,
    run_traced_captured_command: Callable[[list[str]], object],
    json_mode: bool,
    console_print: Callable[[str], None],
    append_project_op: Callable[[str, dict[str, object]], None],
    project_next_json_path: Callable[..., Path],
    load_project_next_candidate: Callable[..., tuple[dict[str, object] | None, dict[str, object] | object]],
    next_command_requires_strict: Callable[[str], bool],
    dispatch_feature_next_command: Callable[..., tuple[str, Callable[[], int]] | None],
    inspect_feature_state: Callable[..., dict[str, object]],
    run_design_cycle: Callable[..., int],
    run_approved_implementation_cycle: Callable[..., int],
    release_gate: Callable[[str, bool], int],
    run_full_flow: Callable[..., int],
    init_feature: Callable[[str], int],
    bootstrap: Callable[[str], int],
    build_approval_summary: Callable[[str], int],
) -> int:
    script = root / "scripts" / "build_project_next.py"
    command = ["python", str(script)]
    if attachment_file:
        command.extend(["--attachment-file", attachment_file])
    if profile:
        command.extend(["--profile", profile])
    result = run_traced_captured_command(command)
    if result.returncode != 0:
        if not json_mode:
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


def run_project_cycle(
    *,
    attachment_file: str | None,
    profile: str | None,
    run_project_console_cycle: Callable[..., int],
    capture_project_cycle_candidates: Callable[..., dict[str, object]],
    run_continue_project_flow_fn: Callable[..., int],
    append_project_op: Callable[[str, dict[str, object]], None],
) -> int:
    before = run_project_console_cycle(attachment_file=attachment_file, profile=profile)
    if before != 0:
        append_project_op("project-cycle", {"result": "fail", "failed_step": "project-console-cycle(before)"})
        return before

    before_snapshot = capture_project_cycle_candidates(attachment_file=attachment_file, profile=profile)
    continue_code = run_continue_project_flow_fn(attachment_file=attachment_file, profile=profile)
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
