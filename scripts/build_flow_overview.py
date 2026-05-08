#!/usr/bin/env python3
"""
build_flow_overview.py

Build project-level flow status overview artifacts.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from attached_project import DEFAULT_ATTACHMENT_PATH
from concurrency import atomic_write_text, path_lock
from flow_state import inspect_feature_state
from json_io import write_json
from project_artifact_paths import describe_active_project_artifacts, get_active_project_artifacts_dir
from versioning import iter_feature_dirs


def render_markdown(states: list[dict[str, object]], project_context: dict[str, object]) -> str:
    stage_counter = Counter(str(state.get("current_stage", "unknown")) for state in states)
    source_counter = Counter(str(state.get("state_source", "unknown")) for state in states)
    lines = [
        "# Project Flow Overview",
        "",
        f"- Feature count: `{len(states)}`",
        "",
        "## Project Context",
        "",
        f"- Project ID: `{project_context.get('project_id')}`",
        f"- Project Name: `{project_context.get('project_name')}`",
        f"- Artifacts Dir: `{project_context.get('artifacts_dir')}`",
        "",
        "## Stage Distribution",
        "",
    ]

    for stage, count in sorted(stage_counter.items()):
        lines.append(f"- `{stage}`: {count}")

    lines.extend(
        [
            "",
            "## State Sources",
            "",
        ]
    )
    for source, count in sorted(source_counter.items()):
        lines.append(f"- `{source}`: {count}")

    lines.extend(
        [
            "",
            "## Features",
            "",
            "| Feature | Stage | Source | Risk | Approval | gate2 | gate3 | gate4 | gate5 | Missing | Blockers | Next |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )

    for state in states:
        feature_name = str(state.get("feature_name", "N/A"))
        stage = str(state.get("current_stage", "N/A"))
        source = str(state.get("state_source", "N/A"))
        risk_tier = str(state.get("risk_tier", "N/A"))
        approval = str(state.get("approval_status", "N/A"))
        gate2 = str(state.get("gate2_result", "N/A"))
        gate3 = str(state.get("gate3_result", "N/A"))
        gate4 = str(state.get("gate4_result", "N/A"))
        gate5 = str(state.get("gate5_result", "N/A"))
        missing = len(state.get("missing_artifacts", [])) if isinstance(state.get("missing_artifacts"), list) else 0
        blockers = len(state.get("blockers", [])) if isinstance(state.get("blockers"), list) else 0
        next_command = str(state.get("next_command", "N/A")).replace("|", "\\|")
        lines.append(
            f"| {feature_name} | {stage} | {source} | {risk_tier} | {approval} | {gate2} | {gate3} | {gate4} | {gate5} | {missing} | {blockers} | `{next_command}` |"
        )

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for project-level overview artifacts.",
    )
    parser.add_argument(
        "--attachment-file",
        default=str(DEFAULT_ATTACHMENT_PATH),
        help="Attachment config path used to resolve design roots and artifact buckets.",
    )
    parser.add_argument("--profile", default=None, help="Optional attachment profile name.")
    args = parser.parse_args()

    attachment_path = Path(args.attachment_file)
    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else get_active_project_artifacts_dir(attachment_path=attachment_path, profile=args.profile, create=True)
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    states = [inspect_feature_state(feature_dir) for feature_dir in iter_feature_dirs(attachment_path=attachment_path, profile=args.profile)]
    project_context = describe_active_project_artifacts(attachment_path=attachment_path, profile=args.profile, create=True)
    payload = {
        "project": project_context,
        "feature_count": len(states),
        "state_source_policy": "prefer_persisted",
        "state_source_counts": dict(Counter(str(state.get("state_source", "unknown")) for state in states)),
        "features": states,
    }

    json_path = output_dir / "flow-overview.json"
    md_path = output_dir / "flow-overview.md"

    with path_lock(output_dir, phase="build-flow-overview"):
        write_json(json_path, payload)
        atomic_write_text(md_path, render_markdown(states, project_context), encoding="utf-8")

    print("[OK] flow-overview generated")
    print(f"  - json: {json_path}")
    print(f"  - md:   {md_path}")
    print(f"  - features: {len(states)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
