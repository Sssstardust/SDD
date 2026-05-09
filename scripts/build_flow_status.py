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
    evidence = state.get("implementation_framework_evidence")
    evidence_parts: list[str] = []
    if isinstance(evidence, dict):
        inherited = evidence.get("inherited_matches")
        mybatis = evidence.get("mybatis_bound_matches")
        result_maps = evidence.get("mybatis_result_map_matches")
        if isinstance(inherited, int) and inherited > 0:
            evidence_parts.append(f"inherit={inherited}")
        if isinstance(mybatis, int) and mybatis > 0:
            evidence_parts.append(f"mybatis={mybatis}")
        if isinstance(result_maps, int) and result_maps > 0:
            evidence_parts.append(f"resultMap={result_maps}")
    claim_brief = state.get("design_resource_claim_brief")
    claim_parts: list[str] = []
    if isinstance(claim_brief, dict):
        counts_by_kind = claim_brief.get("counts_by_kind")
        if isinstance(counts_by_kind, dict):
            operation_count = counts_by_kind.get("operation")
            schema_table_count = counts_by_kind.get("schema-table")
            if isinstance(operation_count, int) and operation_count > 0:
                claim_parts.append(f"operation={operation_count}")
            if isinstance(schema_table_count, int) and schema_table_count > 0:
                claim_parts.append(f"schema-table={schema_table_count}")
        operation_components = claim_brief.get("operation_components")
        if isinstance(operation_components, list) and operation_components:
            claim_parts.append("op.components=" + ",".join(str(item) for item in operation_components[:2]))
        schema_components = claim_brief.get("schema_table_components")
        if isinstance(schema_components, list) and schema_components:
            claim_parts.append("table.components=" + ",".join(str(item) for item in schema_components[:2]))
    resolution_parts: list[str] = []
    missing_method_details = state.get("implementation_missing_method_details")
    if isinstance(missing_method_details, list) and missing_method_details:
        first = missing_method_details[0]
        if isinstance(first, dict):
            class_name = str(first.get("class_name") or "")
            signature = str(first.get("expected_signature") or "")
            resource_key = str(first.get("resource_key") or "")
            preview = ".".join(item for item in (class_name, signature) if item)
            if resource_key:
                preview = f"{preview} @ {resource_key}"
            if preview:
                resolution_parts.append(f"missing={preview}")
    ambiguous_classes = state.get("implementation_ambiguous_classes")
    if isinstance(ambiguous_classes, list) and ambiguous_classes:
        first = ambiguous_classes[0]
        if isinstance(first, dict):
            class_name = str(first.get("class_name") or "")
            components = first.get("candidate_components")
            if class_name:
                suffix = ""
                if isinstance(components, list) and components:
                    suffix = " @ " + ",".join(str(item) for item in components[:2])
                resolution_parts.append(f"ambiguousClass={class_name}{suffix}")
    table_brief = state.get("schema_table_resolution_brief")
    if isinstance(table_brief, dict) and table_brief.get("ambiguous_count"):
        table_name = str(table_brief.get("first_ambiguous_table") or "")
        components = table_brief.get("first_ambiguous_table_components")
        if table_name:
            suffix = ""
            if isinstance(components, list) and components:
                suffix = " @ " + ",".join(str(item) for item in components[:2])
            resolution_parts.append(f"ambiguousTable={table_name}{suffix}")
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
        f"- `implementation`: `{state.get('implementation_result', 'N/A')}`",
        f"- `release_gate`: `{state.get('release_gate_result', 'N/A')}`",
        "",
        "## Implementation Signals",
        "",
        f"- Framework Evidence: `{', '.join(evidence_parts) if evidence_parts else 'N/A'}`",
        f"- Resource Claims: `{'; '.join(claim_parts) if claim_parts else 'N/A'}`",
        f"- Resolution Preview: `{'; '.join(resolution_parts) if resolution_parts else 'N/A'}`",
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
