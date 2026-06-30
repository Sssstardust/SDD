#!/usr/bin/env python3
"""
build_flow_status.py

Refresh feature flow status artifacts from the latest computed project state.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sdd_core.domain.attached_project import DEFAULT_ATTACHMENT_PATH
from sdd_core.infrastructure.concurrency import atomic_write_text, feature_lock
from sdd_core.infrastructure.gate_cache import DESIGN_GATE_NAMES, IMPLEMENTATION_GATE_NAMES, design_gate_input_hash, implementation_gate_input_hash, load_gate_result_from_report, read_design_gate_cache_from_state, update_design_gate_cache
from sdd_core.application.flow_state import compute_feature_state, write_project_state
from sdd_core.application.state_view import affected_component_execution_badge, attached_execution_admission_badge, framework_badges, gate3_ai_review_badge, gate5_admission_summary_badge, gate_cache_badge, real_test_admission_badge, resolution_preview, resource_claim_badges
from sdd_core.infrastructure.versioning import resolve_feature_dir


README_STATUS_BEGIN = "<!-- SDD:STATUS:BEGIN -->"
README_STATUS_END = "<!-- SDD:STATUS:END -->"


def _fmt(value: object, default: str = "N/A") -> str:
    if value is None or value == "":
        return default
    return str(value)


def render_readme_status_block(state: dict[str, object]) -> str:
    next_command = state.get("next_command")
    next_action = "暂无，当前无待执行命令。" if not next_command else str(next_command)
    return "\n".join(
        [
            README_STATUS_BEGIN,
            "## 当前状态",
            "",
            f"- 当前阶段: `{_fmt(state.get('current_stage'))}`",
            f"- 下一步动作: `{next_action}`",
            f"- 风险等级: `{_fmt(state.get('risk_tier'))}`",
            f"- 设计版本: `{_fmt(state.get('design_version'))}`",
            "",
            "## 门禁状态",
            "",
            "| Gate | 状态 |",
            "| --- | --- |",
            f"| Gate 2 | `{_fmt(state.get('gate2_result'))}` |",
            f"| Gate 3 | `{_fmt(state.get('gate3_result'))}` |",
            f"| Gate 4 | `{_fmt(state.get('gate4_result'))}` |",
            f"| Gate 5 | `{_fmt(state.get('gate5_result'))}` |",
            f"| Implementation | `{_fmt(state.get('implementation_result'))}` |",
            f"| Release Gate | `{_fmt(state.get('release_gate_result'))}` |",
            README_STATUS_END,
        ]
    )


def refresh_readme_status(feature_dir: Path, state: dict[str, object]) -> Path | None:
    readme_path = feature_dir / "README.md"
    if not readme_path.exists():
        return None

    content = readme_path.read_text(encoding="utf-8")
    status_block = render_readme_status_block(state)
    if README_STATUS_BEGIN in content and README_STATUS_END in content:
        start = content.index(README_STATUS_BEGIN)
        end = content.index(README_STATUS_END, start) + len(README_STATUS_END)
        updated = content[:start].rstrip() + "\n\n" + status_block + "\n\n" + content[end:].lstrip()
    else:
        lines = content.splitlines()
        insert_at = 2 if len(lines) >= 2 else len(lines)
        updated_lines = lines[:insert_at] + ["", status_block, ""] + lines[insert_at:]
        updated = "\n".join(updated_lines).rstrip() + "\n"

    atomic_write_text(readme_path, updated, encoding="utf-8")
    return readme_path


def render_markdown(state: dict[str, object]) -> str:
    lines = [
        f"# Flow Status: {state.get('feature_name')}",
        "",
        f"- Current Stage: `{state.get('current_stage')}`",
        f"- Risk Tier: `{state.get('risk_tier')}`",
        f"- Strict Recommended: `{state.get('strict_recommended')}`",
        f"- Strict Next Step: `{state.get('strict_next_step')}`",
        f"- Design Version: `{state.get('design_version', 'N/A')}`",
        f"- Approval Status: `{state.get('approval_status', 'N/A')}`",
        "",
        "## Gate Results",
        "",
        f"- `gate2`: `{state.get('gate2_result', 'N/A')}`",
        f"- `gate3`: `{state.get('gate3_result', 'N/A')}`",
        f"- `gate4`: `{state.get('gate4_result', 'N/A')}`",
        f"- `gate5`: `{state.get('gate5_result', 'N/A')}`",
        f"- `implementation`: `{state.get('implementation_result', 'N/A')}`",
        f"- `release_gate`: `{state.get('release_gate_result', 'N/A')}`",
        f"- `gate_cache`: `{gate_cache_badge(state)}`",
        "",
        "## Implementation Signals",
        "",
        f"- Gate 3 AI Review: `{gate3_ai_review_badge(state)}`",
        f"- Gate 5 Admission Summary: `{gate5_admission_summary_badge(state)}`",
        f"- Framework Evidence: `{framework_badges(state)}`",
        f"- Real Test Admission: `{real_test_admission_badge(state)}`",
        f"- Attached Execution Admission: `{attached_execution_admission_badge(state)}`",
        f"- Affected Component Execution: `{affected_component_execution_badge(state)}`",
        f"- Resource Claims: `{resource_claim_badges(state)}`",
        f"- Resolution Preview: `{resolution_preview(state)}`",
        "",
        "## Missing Artifacts",
        "",
    ]

    missing = state.get("missing_artifacts") if isinstance(state.get("missing_artifacts"), list) else []
    if missing:
        lines.extend([f"- `{item}`" for item in missing])
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Blockers",
            "",
        ]
    )
    blockers = state.get("blockers") if isinstance(state.get("blockers"), list) else []
    if blockers:
        lines.extend([f"- {item}" for item in blockers])
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Next Action",
            "",
            f"- Reason: {state.get('reason', 'N/A')}",
            f"- Command: `{state.get('next_command', 'N/A')}`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_dir", help="Path to specs/<feature>")
    parser.add_argument(
        "--attachment-file",
        default=None,
        help="Optional attachment config path used to resolve relative feature paths.",
    )
    parser.add_argument("--profile", default=None, help="Optional attachment profile name.")
    args = parser.parse_args()

    feature_dir = resolve_feature_dir(
        args.feature_dir,
        attachment_path=Path(args.attachment_file) if args.attachment_file else DEFAULT_ATTACHMENT_PATH,
        profile=args.profile,
    )
    if not feature_dir.exists():
        print(f"[ERROR] feature directory does not exist: {feature_dir}")
        return 1

    with feature_lock(feature_dir, phase="build-flow-status"):
        state = compute_feature_state(feature_dir)
        existing_cache = read_design_gate_cache_from_state(state)
        gate_cache = dict(existing_cache)
        for gate_name in (*DESIGN_GATE_NAMES, *IMPLEMENTATION_GATE_NAMES):
            result, report_path = load_gate_result_from_report(feature_dir, gate_name)
            if not result or not report_path:
                continue
            gate_cache = update_design_gate_cache(
                gate_cache,
                gate_name=gate_name,
                status=result,
                input_hash=design_gate_input_hash(feature_dir, gate_name)
                if gate_name in DESIGN_GATE_NAMES
                else implementation_gate_input_hash(feature_dir, gate_name),
                report_path=report_path,
            )
        state["gate_cache"] = gate_cache
        project_state_json_path = write_project_state(feature_dir, state)
        flow_status_md_path = feature_dir / "流程看板.md"

        atomic_write_text(flow_status_md_path, render_markdown(state), encoding="utf-8")
        readme_path = refresh_readme_status(feature_dir, state)

    print("[OK] flow status refreshed")
    print(f"  - project-state: {project_state_json_path}")
    print(f"  - flow-status md:   {flow_status_md_path}")
    if readme_path:
        print(f"  - README status:    {readme_path}")
    print(f"  - next: {state.get('next_command')}")

    if state.get("implementation_result") != "PASS":
        # ANSI escape codes for red bold text
        print("\033[1;31m")
        print("!" * 80)
        print("[CRITICAL] IMPLEMENTATION IS NOT PASS!")
        print("Your code changes are not fully verified by Gate 5.")
        print("Please run: python scripts/run_pipeline.py flow-status <feature> --strict")
        print("Ensure all REQ-IDs are covered and TODOs are cleared before delivery.")
        print("!" * 80)
        print("\033[0m")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
