#!/usr/bin/env python3
"""
build_project_next.py

Pick the next best feature to advance at the project level.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from attached_project import DEFAULT_ATTACHMENT_PATH
from concurrency import atomic_write_text, path_lock
from project_output_bundle import build_project_level_payload, resolve_output_dir, write_project_json
from ops_log import read_latest_op
from state_view import affected_component_execution_badge, attached_execution_admission_badge, gate5_admission_summary_badge, real_test_admission_badge, strict_flag, workspace_summary_lines


STAGE_PRIORITY = {
    "uninitialized": 0,
    "bootstrap-needed": 1,
    "feature-brief-ready": 1,
    "design-in-progress": 2,
    "awaiting-approval": 3,
    "approved-ready-for-implementation": 4,
    "implementation-needs-attention": 5,
    "verified-ready-for-release": 6,
    "release-ready": 7,
}


def implementation_attention_summary(state: dict[str, object]) -> dict[str, object]:
    implementation_result = str(state.get("implementation_result") or "")
    evidence = state.get("implementation_framework_evidence")
    if not isinstance(evidence, dict):
        evidence = {}
    inherited = int(evidence.get("inherited_matches", 0) or 0)
    mybatis = int(evidence.get("mybatis_bound_matches", 0) or 0)
    result_maps = int(evidence.get("mybatis_result_map_matches", 0) or 0)
    signal_count = inherited + mybatis + result_maps
    labels: list[str] = []
    if inherited > 0:
        labels.append(f"inherit={inherited}")
    if mybatis > 0:
        labels.append(f"mybatis={mybatis}")
    if result_maps > 0:
        labels.append(f"resultMap={result_maps}")
    missing_method_details = state.get("implementation_missing_method_details")
    if isinstance(missing_method_details, list) and missing_method_details:
        labels.append(f"missingMethod={len(missing_method_details)}")
    real_test_admission = state.get("real_test_req_admission")
    real_test_admission_result = None
    real_test_missing_count = 0
    if isinstance(real_test_admission, dict) and real_test_admission:
        admission_result = str(real_test_admission.get("result") or "").strip()
        missing_req_ids = real_test_admission.get("missing_required_req_ids")
        real_test_admission_result = admission_result or None
        real_test_missing_count = len(missing_req_ids) if isinstance(missing_req_ids, list) else 0
    attached_admission = state.get("attached_execution_admission")
    attached_admission_result = None
    attached_failed_count = 0
    if isinstance(attached_admission, dict) and attached_admission:
        attached_result = str(attached_admission.get("result") or "").strip()
        failed_components = attached_admission.get("failed_components")
        failed_commands = attached_admission.get("failed_commands")
        attached_admission_result = attached_result or None
        if isinstance(failed_components, list) and failed_components:
            attached_failed_count = len(failed_components)
        elif isinstance(failed_commands, list):
            attached_failed_count = len(failed_commands)
    gate5_admission_summary = state.get("gate5_admission_summary")
    gate5_admission_result = None
    if isinstance(gate5_admission_summary, dict) and gate5_admission_summary:
        gate5_admission_result = str(gate5_admission_summary.get("result") or "").strip() or None
    component_admission = state.get("affected_component_execution_admission")
    component_admission_result = None
    component_issue_count = 0
    if isinstance(component_admission, dict) and component_admission:
        component_result = str(component_admission.get("result") or "").strip()
        missing_components = component_admission.get("missing_components")
        failed_components = component_admission.get("failed_components")
        component_admission_result = component_result or None
        component_issue_count = (
            (len(missing_components) if isinstance(missing_components, list) else 0)
            + (len(failed_components) if isinstance(failed_components, list) else 0)
        )
    return {
        "implementation_result": implementation_result or None,
        "real_test_admission_result": real_test_admission_result,
        "real_test_missing_count": real_test_missing_count,
        "attached_admission_result": attached_admission_result,
        "attached_failed_count": attached_failed_count,
        "gate5_admission_result": gate5_admission_result,
        "component_admission_result": component_admission_result,
        "component_issue_count": component_issue_count,
        "signal_count": signal_count,
        "labels": labels,
    }


def missing_method_preview(state: dict[str, object]) -> str | None:
    details = state.get("implementation_missing_method_details")
    if not isinstance(details, list) or not details:
        return None
    first = details[0]
    if not isinstance(first, dict):
        return None
    class_name = str(first.get("class_name") or "").strip()
    expected_signature = str(first.get("expected_signature") or "").strip()
    resource_key = str(first.get("resource_key") or "").strip()
    parts = []
    if class_name:
        parts.append(class_name)
    if expected_signature:
        parts.append(expected_signature)
    preview = ".".join(parts) if len(parts) == 2 else (expected_signature or class_name)
    if resource_key:
        return f"{preview} @ {resource_key}"
    return preview or None


def enrich_candidate_reason(state: dict[str, object]) -> dict[str, object]:
    enriched = dict(state)
    attention = implementation_attention_summary(state)
    missing_preview = missing_method_preview(state)
    base_reason = str(state.get("reason") or "").strip()
    if str(state.get("current_stage")) == "implementation-needs-attention":
        implementation_result = attention.get("implementation_result")
        labels = attention.get("labels", [])
        if implementation_result and implementation_result != "PASS":
            signal_text = f"; framework evidence: {', '.join(labels)}" if labels else ""
            enriched["reason"] = f"{base_reason}; implementation traceability={implementation_result}{signal_text}".strip("; ")
        elif labels:
            enriched["reason"] = f"{base_reason}; framework evidence: {', '.join(labels)}".strip("; ")
        if missing_preview:
            enriched["reason"] = f"{str(enriched.get('reason') or '').strip()}; first missing method: {missing_preview}".strip("; ")
        admission_result = attention.get("real_test_admission_result")
        if admission_result and admission_result != "PASS":
            missing_count = int(attention.get("real_test_missing_count", 0) or 0)
            suffix = f" missingReq={missing_count}" if missing_count else ""
            enriched["reason"] = f"{str(enriched.get('reason') or '').strip()}; real-test admission={admission_result}{suffix}".strip("; ")
        attached_result = attention.get("attached_admission_result")
        if attached_result and attached_result not in {"PASS", "SKIPPED"}:
            failed_count = int(attention.get("attached_failed_count", 0) or 0)
            suffix = f" failed={failed_count}" if failed_count else ""
            enriched["reason"] = f"{str(enriched.get('reason') or '').strip()}; attached execution={attached_result}{suffix}".strip("; ")
        component_result = attention.get("component_admission_result")
        if component_result and component_result != "PASS":
            issue_count = int(attention.get("component_issue_count", 0) or 0)
            suffix = f" issues={issue_count}" if issue_count else ""
            enriched["reason"] = f"{str(enriched.get('reason') or '').strip()}; component execution={component_result}{suffix}".strip("; ")
        summary_result = attention.get("gate5_admission_result")
        if summary_result and summary_result not in {"PASS", "SKIPPED"}:
            enriched["reason"] = f"{str(enriched.get('reason') or '').strip()}; gate5 admission={summary_result}".strip("; ")
    return enriched


def choose_candidate(states: list[dict[str, object]]) -> dict[str, object] | None:
    actionable = [
        state
        for state in states
        if str(state.get("current_stage")) != "release-ready"
        and str(state.get("next_command", "")).strip()
    ]
    if not actionable:
        return None

    def sort_key(state: dict[str, object]) -> tuple[int, int, int, str]:
        stage = str(state.get("current_stage", "unknown"))
        priority = STAGE_PRIORITY.get(stage, 99)
        risk = 0 if str(state.get("risk_tier")) == "high" else 1
        attention = implementation_attention_summary(state)
        implementation_penalty = 0
        if stage == "implementation-needs-attention":
            implementation_result = str(attention.get("implementation_result") or "")
            if (
                implementation_result == "FAIL"
                or str(attention.get("real_test_admission_result") or "") == "FAIL"
                or str(attention.get("attached_admission_result") or "") == "FAIL"
                or str(attention.get("component_admission_result") or "") == "FAIL"
            ):
                implementation_penalty = -3
            elif implementation_result == "WARN":
                implementation_penalty = -2
            elif str(attention.get("real_test_admission_result") or "") == "WARN":
                implementation_penalty = -2
            elif str(attention.get("component_admission_result") or "") == "WARN":
                implementation_penalty = -2
            elif int(attention.get("signal_count", 0) or 0) > 0:
                implementation_penalty = -1
        feature_name = str(state.get("feature_name", ""))
        return (priority, risk, implementation_penalty, feature_name)

    return enrich_candidate_reason(sorted(actionable, key=sort_key)[0])


def render_markdown(
    states: list[dict[str, object]],
    candidate: dict[str, object] | None,
    project_context: dict[str, object],
    workspace: dict[str, object] | None = None,
) -> str:
    latest_execution = read_latest_op(["continue-project-flow", "project-cycle"])
    from collections import Counter

    source_counter = Counter(str(state.get("state_source", "unknown")) for state in states)
    lines = [
        "# Project Next Action",
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
        "## Recent Execution",
        "",
    ]

    if latest_execution:
        lines.append(
            f"- `{latest_execution.get('at')}` `{latest_execution.get('op_type')}` {latest_execution.get('payload', {})}"
        )
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## State Sources",
            "",
        ]
    )
    for source, count in sorted(source_counter.items()):
        lines.append(f"- `{source}`: {count}")

    if candidate is None:
        lines.extend(
            [
                "",
                "- No feature currently needs automatic advancement.",
                "- All tracked features are `release-ready`, or they do not have an actionable next command.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "",
                f"- Recommended feature: `{candidate.get('feature_name')}`",
                f"- Current stage: `{candidate.get('current_stage')}`",
                f"- Source: `{candidate.get('state_source')}`",
                f"- Risk tier: `{candidate.get('risk_tier')}`",
                f"- Strict: `{strict_flag(candidate)}`",
                f"- Implementation result: `{candidate.get('implementation_result')}`",
                f"- Gate5 Admission: `{gate5_admission_summary_badge(candidate)}`",
                f"- Real Test Admission: `{real_test_admission_badge(candidate)}`",
                f"- Attached Execution: `{attached_execution_admission_badge(candidate)}`",
                f"- Component Execution: `{affected_component_execution_badge(candidate)}`",
                f"- Reason: {candidate.get('reason')}",
                f"- Next command: `{candidate.get('next_command')}`",
                "",
            ]
        )

    lines.extend(
        [
            "## Candidates",
            "",
            "| Feature | Stage | Source | Risk | Strict | impl | Gate5 Admission | Real Test Admission | Attached Execution | Component Execution | Framework Evidence | Missing | Blockers | Next |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for state in states:
        feature_name = str(state.get("feature_name", "N/A"))
        stage = str(state.get("current_stage", "N/A"))
        source = str(state.get("state_source", "N/A"))
        risk = str(state.get("risk_tier", "N/A"))
        strict_mode = strict_flag(state)
        implementation_result = str(state.get("implementation_result", "N/A"))
        gate5_admission = gate5_admission_summary_badge(state).replace("|", "\\|")
        real_test_admission = real_test_admission_badge(state).replace("|", "\\|")
        attached_execution_admission = attached_execution_admission_badge(state).replace("|", "\\|")
        component_execution_admission = affected_component_execution_badge(state).replace("|", "\\|")
        attention = implementation_attention_summary(state)
        evidence = ", ".join(str(item) for item in attention.get("labels", [])) or "N/A"
        missing = len(state.get("missing_artifacts", [])) if isinstance(state.get("missing_artifacts"), list) else 0
        blockers = len(state.get("blockers", [])) if isinstance(state.get("blockers"), list) else 0
        next_command = str(state.get("next_command", "N/A")).replace("|", "\\|")
        lines.append(
            f"| {feature_name} | {stage} | {source} | {risk} | {strict_mode} | {implementation_result} | {gate5_admission} | {real_test_admission} | {attached_execution_admission} | {component_execution_admission} | {evidence} | {missing} | {blockers} | `{next_command}` |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for project-level next-step artifacts.",
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
    candidate = choose_candidate(states)
    project_context = payload["project"]
    workspace = payload["workspace"]
    payload["candidate"] = candidate

    json_path = output_dir / "project-next.json"
    md_path = output_dir / "project-next.md"
    with path_lock(output_dir, phase="build-project-next"):
        write_project_json(output_dir, "project-next.json", payload)
        atomic_write_text(md_path, render_markdown(states, candidate, project_context, workspace), encoding="utf-8")

    print("[OK] project-next generated")
    print(f"  - json: {json_path}")
    print(f"  - md:   {md_path}")
    if candidate is not None:
        print(f"  - next: {candidate.get('next_command')}")
    else:
        print("  - next: <none>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
