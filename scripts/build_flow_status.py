#!/usr/bin/env python3
"""
build_flow_status.py

Refresh feature flow status artifacts from the latest computed project state.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from attached_project import DEFAULT_ATTACHMENT_PATH
from concurrency import atomic_write_text, feature_lock
from flow_state import compute_feature_state, write_project_state
from json_io import write_json
from versioning import resolve_feature_dir


def render_markdown(state: dict[str, object]) -> str:
    lines = [
        f"# Flow Status: {state.get('feature_name')}",
        "",
        f"- Current Stage: `{state.get('current_stage')}`",
        f"- Risk Tier: `{state.get('risk_tier')}`",
        f"- Design Version: `{state.get('design_version', 'N/A')}`",
        f"- Approval Status: `{state.get('approval_status', 'N/A')}`",
        "",
        "## Gate Results",
        "",
        f"- `gate2`: `{state.get('gate2_result', 'N/A')}`",
        f"- `gate3`: `{state.get('gate3_result', 'N/A')}`",
        f"- `gate4`: `{state.get('gate4_result', 'N/A')}`",
        f"- `gate5`: `{state.get('gate5_result', 'N/A')}`",
        f"- `release_gate`: `{state.get('release_gate_result', 'N/A')}`",
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
