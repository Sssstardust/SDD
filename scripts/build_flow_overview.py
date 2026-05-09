#!/usr/bin/env python3
"""
build_flow_overview.py

Build project-level flow status overview artifacts.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from attached_project import DEFAULT_ATTACHMENT_PATH
from concurrency import atomic_write_text, path_lock
from project_output_bundle import build_project_level_payload, resolve_output_dir, write_project_json
from state_view import framework_badges, release_exception_badges, resolution_preview, resource_claim_badges, strict_flag, workspace_summary_lines


def render_markdown(states: list[dict[str, object]], project_context: dict[str, object], workspace: dict[str, object] | None = None) -> str:
    from collections import Counter

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
        "## Workspace",
        "",
        *workspace_summary_lines(workspace),
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

    lines.extend(["", "## Resolution Preview", ""])
    for state in states[:10]:
        preview = resolution_preview(state, compact=True)
        if preview == "N/A":
            continue
        lines.append(f"- `{state.get('feature_name')}`: {preview}")

    lines.extend(
        [
            "",
            "## Features",
            "",
            "| Feature | Stage | Source | Risk | Strict | Approval | gate2 | gate3 | gate4 | gate5 | impl | Framework Evidence | Resource Claims | Release Exception | Missing | Blockers | Next |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )

    for state in states:
        feature_name = str(state.get("feature_name", "N/A"))
        stage = str(state.get("current_stage", "N/A"))
        source = str(state.get("state_source", "N/A"))
        risk_tier = str(state.get("risk_tier", "N/A"))
        strict_mode = strict_flag(state)
        approval = str(state.get("approval_status", "N/A"))
        gate2 = str(state.get("gate2_result", "N/A"))
        gate3 = str(state.get("gate3_result", "N/A"))
        gate4 = str(state.get("gate4_result", "N/A"))
        gate5 = str(state.get("gate5_result", "N/A"))
        implementation_result = str(state.get("implementation_result", "N/A"))
        missing = len(state.get("missing_artifacts", [])) if isinstance(state.get("missing_artifacts"), list) else 0
        blockers = len(state.get("blockers", [])) if isinstance(state.get("blockers"), list) else 0
        next_command = str(state.get("next_command", "N/A")).replace("|", "\\|")
        framework_evidence = framework_badges(state).replace("|", "\\|")
        resource_claims = resource_claim_badges(state).replace("|", "\\|")
        release_exception = release_exception_badges(state).replace("|", "\\|")
        lines.append(
            f"| {feature_name} | {stage} | {source} | {risk_tier} | {strict_mode} | {approval} | {gate2} | {gate3} | {gate4} | {gate5} | {implementation_result} | {framework_evidence} | {resource_claims} | {release_exception} | {missing} | {blockers} | `{next_command}` |"
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
    output_dir = resolve_output_dir(output_dir=args.output_dir, attachment_path=attachment_path, profile=args.profile)
    payload = build_project_level_payload(attachment_path=attachment_path, profile=args.profile)
    states = payload["features"]
    project_context = payload["project"]
    workspace = payload["workspace"]

    json_path = output_dir / "flow-overview.json"
    md_path = output_dir / "flow-overview.md"

    with path_lock(output_dir, phase="build-flow-overview"):
        write_project_json(output_dir, "flow-overview.json", payload)
        atomic_write_text(md_path, render_markdown(states, project_context, workspace), encoding="utf-8")

    print("[OK] flow-overview generated")
    print(f"  - json: {json_path}")
    print(f"  - md:   {md_path}")
    print(f"  - features: {len(states)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
