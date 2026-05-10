#!/usr/bin/env python3
"""
build_flow_status.py

Refresh feature flow status artifacts from the latest computed project state.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from domain.attached_project import DEFAULT_ATTACHMENT_PATH
from infrastructure.concurrency import atomic_write_text, feature_lock
from infrastructure.gate_cache import DESIGN_GATE_NAMES, IMPLEMENTATION_GATE_NAMES, design_gate_input_hash, implementation_gate_input_hash, load_gate_result_from_report, read_design_gate_cache_from_state, update_design_gate_cache
from application.flow_state import compute_feature_state, write_project_state
from infrastructure.json_io import write_json
from application.state_view import affected_component_execution_badge, attached_execution_admission_badge, framework_badges, gate3_ai_review_badge, gate5_admission_summary_badge, gate_cache_badge, real_test_admission_badge, resolution_preview, resource_claim_badges
from infrastructure.versioning import resolve_feature_dir


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
        flow_status_json_path = feature_dir / "flow-status.json"
        flow_status_md_path = feature_dir / "flow-status.md"

        write_json(flow_status_json_path, state)
        atomic_write_text(flow_status_md_path, render_markdown(state), encoding="utf-8")

    print("[OK] flow status refreshed")
    print(f"  - project-state: {project_state_json_path}")
    print(f"  - flow-status json: {flow_status_json_path}")
    print(f"  - flow-status md:   {flow_status_md_path}")
    print(f"  - next: {state.get('next_command')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
