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
    def framework_badges(state: dict[str, object]) -> str:
        evidence = state.get("implementation_framework_evidence")
        if not isinstance(evidence, dict) or not evidence:
            return "N/A"
        parts: list[str] = []
        inherited = evidence.get("inherited_matches")
        mybatis = evidence.get("mybatis_bound_matches")
        result_maps = evidence.get("mybatis_result_map_matches")
        if isinstance(inherited, int) and inherited > 0:
            parts.append(f"inherit={inherited}")
        if isinstance(mybatis, int) and mybatis > 0:
            parts.append(f"mybatis={mybatis}")
        if isinstance(result_maps, int) and result_maps > 0:
            parts.append(f"resultMap={result_maps}")
        missing_method_details = state.get("implementation_missing_method_details")
        if isinstance(missing_method_details, list) and missing_method_details:
            parts.append(f"missingMethod={len(missing_method_details)}")
        return ", ".join(parts) if parts else "N/A"

    def claim_badges(state: dict[str, object]) -> str:
        claim_brief = state.get("design_resource_claim_brief")
        if not isinstance(claim_brief, dict):
            return "N/A"
        parts: list[str] = []
        counts_by_kind = claim_brief.get("counts_by_kind")
        if isinstance(counts_by_kind, dict):
            operation_count = counts_by_kind.get("operation")
            schema_table_count = counts_by_kind.get("schema-table")
            if isinstance(operation_count, int) and operation_count > 0:
                parts.append(f"op={operation_count}")
            if isinstance(schema_table_count, int) and schema_table_count > 0:
                parts.append(f"table={schema_table_count}")
        operation_components = claim_brief.get("operation_components")
        if isinstance(operation_components, list) and operation_components:
            parts.append("op@" + ",".join(str(item) for item in operation_components[:2]))
        schema_components = claim_brief.get("schema_table_components")
        if isinstance(schema_components, list) and schema_components:
            parts.append("tbl@" + ",".join(str(item) for item in schema_components[:2]))
        return ", ".join(parts) if parts else "N/A"

    def resolution_preview(state: dict[str, object]) -> str:
        parts: list[str] = []
        missing_method_details = state.get("implementation_missing_method_details")
        if isinstance(missing_method_details, list) and missing_method_details:
            first = missing_method_details[0]
            if isinstance(first, dict):
                class_name = str(first.get("class_name") or "")
                signature = str(first.get("expected_signature") or "")
                if class_name or signature:
                    parts.append(f"missing={'.'.join(item for item in (class_name, signature) if item)}")
        ambiguous_classes = state.get("implementation_ambiguous_classes")
        if isinstance(ambiguous_classes, list) and ambiguous_classes:
            first = ambiguous_classes[0]
            if isinstance(first, dict) and first.get("class_name"):
                parts.append(f"ambiguousClass={first.get('class_name')}")
        table_brief = state.get("schema_table_resolution_brief")
        if isinstance(table_brief, dict) and table_brief.get("ambiguous_count") and table_brief.get("first_ambiguous_table"):
            parts.append(f"ambiguousTable={table_brief.get('first_ambiguous_table')}")
        return "; ".join(parts) if parts else "N/A"

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

    lines.extend(["", "## Resolution Preview", ""])
    for state in states[:10]:
        preview = resolution_preview(state)
        if preview == "N/A":
            continue
        lines.append(f"- `{state.get('feature_name')}`: {preview}")

    lines.extend(
        [
            "",
            "## Features",
            "",
            "| Feature | Stage | Source | Risk | Approval | gate2 | gate3 | gate4 | gate5 | impl | Framework Evidence | Resource Claims | Missing | Blockers | Next |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
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
        implementation_result = str(state.get("implementation_result", "N/A"))
        missing = len(state.get("missing_artifacts", [])) if isinstance(state.get("missing_artifacts"), list) else 0
        blockers = len(state.get("blockers", [])) if isinstance(state.get("blockers"), list) else 0
        next_command = str(state.get("next_command", "N/A")).replace("|", "\\|")
        framework_evidence = framework_badges(state).replace("|", "\\|")
        resource_claims = claim_badges(state).replace("|", "\\|")
        lines.append(
            f"| {feature_name} | {stage} | {source} | {risk_tier} | {approval} | {gate2} | {gate3} | {gate4} | {gate5} | {implementation_result} | {framework_evidence} | {resource_claims} | {missing} | {blockers} | `{next_command}` |"
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
