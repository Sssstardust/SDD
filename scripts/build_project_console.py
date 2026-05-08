#!/usr/bin/env python3
"""
build_project_console.py

Build project-level console artifacts.
"""

from __future__ import annotations

import argparse
from collections import Counter
from html import escape
from pathlib import Path

from attached_project import DEFAULT_ATTACHMENT_PATH
from build_project_next import choose_candidate
from flow_state import inspect_feature_state
from json_io import read_json, write_json
from ops_log import read_latest_op, read_recent_ops
from project_artifact_paths import describe_active_project_artifacts, get_active_project_artifacts_dir
from versioning import iter_feature_dirs


def render_markdown(
    states: list[dict[str, object]],
    candidate: dict[str, object] | None,
    hygiene_payload: dict[str, object] | None,
    project_context: dict[str, object],
) -> str:
    stage_counter = Counter(str(state.get("current_stage", "unknown")) for state in states)
    source_counter = Counter(str(state.get("state_source", "unknown")) for state in states)
    lines = [
        "# Project Console",
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

    lines.extend(["", "## Current Recommendation", ""])
    if candidate is None:
        lines.append("- No feature currently needs automatic advancement.")
    else:
        lines.extend(
            [
                f"- Feature: `{candidate.get('feature_name')}`",
                f"- Stage: `{candidate.get('current_stage')}`",
                f"- Source: `{candidate.get('state_source')}`",
                f"- Risk: `{candidate.get('risk_tier')}`",
                f"- Reason: {candidate.get('reason')}",
                f"- Command: `{candidate.get('next_command')}`",
            ]
        )

    recent_ops = read_recent_ops(10)
    latest_execution = read_latest_op(["continue-project-flow", "project-cycle"])

    lines.extend(["", "## Recent Execution", ""])
    if latest_execution:
        lines.append(
            f"- `{latest_execution.get('at')}` `{latest_execution.get('op_type')}` {latest_execution.get('payload', {})}"
        )
    else:
        lines.append("- None")

    lines.extend(["", "## Recent Operations", ""])
    if recent_ops:
        for entry in reversed(recent_ops):
            lines.append(f"- `{entry.get('at')}` `{entry.get('op_type')}` {entry.get('payload', {})}")
    else:
        lines.append("- None")

    lines.extend(["", "## Tooling Hygiene", ""])
    if hygiene_payload is None:
        lines.append("- tooling-hygiene artifact is not available yet.")
    else:
        issue_count = int(hygiene_payload.get("issue_count", 0))
        lines.append(f"- Issue count: `{issue_count}`")
        issues = hygiene_payload.get("issues")
        if isinstance(issues, list) and issues:
            for issue in issues[:5]:
                if isinstance(issue, dict):
                    lines.append(f"- [{issue.get('severity', 'info')}] {issue.get('path')} - {issue.get('message')}")
        elif issue_count == 0:
            lines.append("- No obvious generated-artifact or workspace hygiene issues were found.")

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
        missing = len(state.get("missing_artifacts", [])) if isinstance(state.get("missing_artifacts"), list) else 0
        blockers = len(state.get("blockers", [])) if isinstance(state.get("blockers"), list) else 0
        next_command = str(state.get("next_command", "N/A")).replace("|", "\\|")
        lines.append(
            f"| {state.get('feature_name')} | {state.get('current_stage')} | {state.get('state_source')} | {state.get('risk_tier')} | "
            f"{state.get('approval_status')} | {state.get('gate2_result')} | {state.get('gate3_result')} | "
            f"{state.get('gate4_result')} | {state.get('gate5_result')} | {missing} | {blockers} | `{next_command}` |"
        )

    lines.append("")
    return "\n".join(lines)


def render_html(
    states: list[dict[str, object]],
    candidate: dict[str, object] | None,
    hygiene_payload: dict[str, object] | None,
    project_context: dict[str, object],
) -> str:
    stage_counter = Counter(str(state.get("current_stage", "unknown")) for state in states)
    source_counter = Counter(str(state.get("state_source", "unknown")) for state in states)
    recent_ops = read_recent_ops(10)
    latest_execution = read_latest_op(["continue-project-flow", "project-cycle"])

    def list_items(counter: Counter[str]) -> str:
        return "".join(
            f"<li><strong>{escape(key)}</strong><span>{value}</span></li>"
            for key, value in sorted(counter.items())
        )

    def feature_rows() -> str:
        rows: list[str] = []
        for state in states:
            missing = len(state.get("missing_artifacts", [])) if isinstance(state.get("missing_artifacts"), list) else 0
            blockers = len(state.get("blockers", [])) if isinstance(state.get("blockers"), list) else 0
            rows.append(
                "<tr>"
                f"<td>{escape(str(state.get('feature_name')))}</td>"
                f"<td>{escape(str(state.get('current_stage')))}</td>"
                f"<td>{escape(str(state.get('state_source')))}</td>"
                f"<td>{escape(str(state.get('risk_tier')))}</td>"
                f"<td>{escape(str(state.get('approval_status')))}</td>"
                f"<td>{escape(str(state.get('gate2_result')))}</td>"
                f"<td>{escape(str(state.get('gate3_result')))}</td>"
                f"<td>{escape(str(state.get('gate4_result')))}</td>"
                f"<td>{escape(str(state.get('gate5_result')))}</td>"
                f"<td>{missing}</td>"
                f"<td>{blockers}</td>"
                f"<td><code>{escape(str(state.get('next_command')))}</code></td>"
                "</tr>"
            )
        return "".join(rows)

    def operations_html() -> str:
        if not recent_ops:
            return "<li>None</li>"
        return "".join(
            f"<li><code>{escape(str(entry.get('at')))}</code> "
            f"<strong>{escape(str(entry.get('op_type')))}</strong> "
            f"{escape(str(entry.get('payload')))}</li>"
            for entry in reversed(recent_ops)
        )

    hygiene_issues = []
    if isinstance(hygiene_payload, dict):
        raw_issues = hygiene_payload.get("issues")
        if isinstance(raw_issues, list):
            hygiene_issues = [issue for issue in raw_issues if isinstance(issue, dict)]

    candidate_html = (
        "<p>No feature currently needs automatic advancement.</p>"
        if candidate is None
        else (
            f"<ul>"
            f"<li><strong>Feature:</strong> {escape(str(candidate.get('feature_name')))}</li>"
            f"<li><strong>Stage:</strong> {escape(str(candidate.get('current_stage')))}</li>"
            f"<li><strong>Source:</strong> {escape(str(candidate.get('state_source')))}</li>"
            f"<li><strong>Risk:</strong> {escape(str(candidate.get('risk_tier')))}</li>"
            f"<li><strong>Reason:</strong> {escape(str(candidate.get('reason')))}</li>"
            f"<li><strong>Command:</strong> <code>{escape(str(candidate.get('next_command')))}</code></li>"
            f"</ul>"
        )
    )
    latest_execution_text = escape(str(latest_execution)) if latest_execution else "None"
    hygiene_html = (
        "<ul>"
        + "".join(
            f"<li>[{escape(str(issue.get('severity', 'info')))}] {escape(str(issue.get('path')))} - {escape(str(issue.get('message')))}</li>"
            for issue in hygiene_issues[:5]
        )
        + "</ul>"
        if hygiene_issues
        else "<p>No obvious generated-artifact or workspace hygiene issues were found.</p>"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Project Console</title>
  <style>
    :root {{
      --bg: #f4f1ea;
      --panel: #fffdf8;
      --ink: #1f2933;
      --muted: #52606d;
      --line: #d9d2c3;
      --accent: #8f3b2e;
      --accent-soft: #f8e8dc;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 32px;
      background: linear-gradient(180deg, #f9f4ec 0%, var(--bg) 100%);
      color: var(--ink);
      font: 14px/1.5 "Segoe UI", sans-serif;
    }}
    h1, h2 {{ margin: 0 0 12px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 16px;
      margin: 20px 0 28px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 18px;
      box-shadow: 0 10px 30px rgba(31, 41, 51, 0.06);
    }}
    .hero {{
      background: radial-gradient(circle at top right, #f8d9b7 0%, var(--panel) 50%);
    }}
    .metric {{
      font-size: 28px;
      font-weight: 700;
      color: var(--accent);
    }}
    ul {{ margin: 0; padding-left: 18px; }}
    .chips {{ list-style: none; padding: 0; margin: 0; }}
    .chips li {{
      display: flex;
      justify-content: space-between;
      padding: 8px 0;
      border-bottom: 1px dashed var(--line);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 16px;
      overflow: hidden;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: var(--accent-soft);
      color: var(--ink);
    }}
    code {{
      color: var(--accent);
      white-space: pre-wrap;
    }}
    .section {{ margin-bottom: 28px; }}
    .muted {{ color: var(--muted); }}
  </style>
</head>
<body>
  <section class="card hero">
    <h1>Project Console</h1>
    <p class="muted">Project ID: <strong>{escape(str(project_context.get("project_id")))}</strong></p>
    <p class="muted">Project Name: <strong>{escape(str(project_context.get("project_name")))}</strong></p>
    <p class="muted">Artifacts Dir: <code>{escape(str(project_context.get("artifacts_dir")))}</code></p>
  </section>

  <section class="grid">
    <article class="card">
      <h2>Feature Count</h2>
      <div class="metric">{len(states)}</div>
    </article>
    <article class="card">
      <h2>Stage Distribution</h2>
      <ul class="chips">{list_items(stage_counter)}</ul>
    </article>
    <article class="card">
      <h2>State Sources</h2>
      <ul class="chips">{list_items(source_counter)}</ul>
    </article>
  </section>

  <section class="section card">
    <h2>Current Recommendation</h2>
    {candidate_html}
  </section>

  <section class="grid">
    <article class="card">
      <h2>Latest Execution</h2>
      <p>{latest_execution_text}</p>
    </article>
    <article class="card">
      <h2>Tooling Hygiene</h2>
      {hygiene_html}
    </article>
  </section>

  <section class="section card">
    <h2>Recent Operations</h2>
    <ul>{operations_html()}</ul>
  </section>

  <section class="section">
    <h2>Features</h2>
    <table>
      <thead>
        <tr>
          <th>Feature</th>
          <th>Stage</th>
          <th>Source</th>
          <th>Risk</th>
          <th>Approval</th>
          <th>gate2</th>
          <th>gate3</th>
          <th>gate4</th>
          <th>gate5</th>
          <th>Missing</th>
          <th>Blockers</th>
          <th>Next</th>
        </tr>
      </thead>
      <tbody>{feature_rows()}</tbody>
    </table>
  </section>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for project-level console artifacts.",
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
    candidate = choose_candidate(states)
    project_context = describe_active_project_artifacts(attachment_path=attachment_path, profile=args.profile, create=True)
    hygiene_path = output_dir / "tooling-hygiene.json"
    if not hygiene_path.exists():
        hygiene_path = output_dir / "workspace-hygiene.json"
    hygiene_payload = read_json(hygiene_path) if hygiene_path.exists() else None

    payload = {
        "project": project_context,
        "feature_count": len(states),
        "stage_counts": dict(Counter(str(state.get("current_stage", "unknown")) for state in states)),
        "state_source_policy": "prefer_persisted",
        "state_source_counts": dict(Counter(str(state.get("state_source", "unknown")) for state in states)),
        "candidate": candidate,
        "latest_execution": read_latest_op(["continue-project-flow", "project-cycle"]),
        "recent_ops": read_recent_ops(10),
        "tooling_hygiene": hygiene_payload,
        "workspace_hygiene": hygiene_payload,
        "features": states,
    }

    json_path = output_dir / "project-console.json"
    md_path = output_dir / "project-console.md"
    html_path = output_dir / "project-console.html"
    write_json(json_path, payload)
    md_path.write_text(
        render_markdown(
            states,
            candidate,
            hygiene_payload if isinstance(hygiene_payload, dict) else None,
            project_context,
        ),
        encoding="utf-8",
    )
    html_path.write_text(
        render_html(
            states,
            candidate,
            hygiene_payload if isinstance(hygiene_payload, dict) else None,
            project_context,
        ),
        encoding="utf-8",
    )

    print("[OK] project-console generated")
    print(f"  - json: {json_path}")
    print(f"  - md:   {md_path}")
    print(f"  - html: {html_path}")
    if candidate is not None:
        print(f"  - next: {candidate.get('next_command')}")
    else:
        print("  - next: <none>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
