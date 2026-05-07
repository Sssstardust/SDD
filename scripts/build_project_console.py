#!/usr/bin/env python3
"""
build_project_console.py

生成项目级主流程控制台产物：
- project-console.json
- project-console.md
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from build_project_next import choose_candidate, iter_feature_dirs
from flow_state import inspect_feature_state
from json_io import read_json
from ops_log import read_latest_op, read_recent_ops
from project_artifact_paths import get_active_project_artifacts_dir


ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = get_active_project_artifacts_dir(create=True)


def render_markdown(
    states: list[dict[str, object]],
    candidate: dict[str, object] | None,
    hygiene_payload: dict[str, object] | None,
) -> str:
    stage_counter = Counter(str(state.get("current_stage", "unknown")) for state in states)

    lines = [
        "# Project Console",
        "",
        f"- feature 数量：`{len(states)}`",
        "",
        "## 阶段分布",
        "",
    ]
    for stage, count in sorted(stage_counter.items()):
        lines.append(f"- `{stage}`: {count}")

    lines.extend(["", "## 当前推荐", ""])
    if candidate is None:
        lines.append("- 当前没有需要自动推进的 feature。")
    else:
        lines.extend(
            [
                f"- feature：`{candidate.get('feature_name')}`",
                f"- 阶段：`{candidate.get('current_stage')}`",
                f"- 风险：`{candidate.get('risk_tier')}`",
                f"- 原因：{candidate.get('reason')}",
                f"- 命令：`{candidate.get('next_command')}`",
            ]
        )

    recent_ops = read_recent_ops(10)
    latest_execution = read_latest_op(["continue-project-flow", "project-cycle"])

    lines.extend(["", "## 最近推进结果", ""])
    if latest_execution:
        lines.append(f"- `{latest_execution.get('at')}` `{latest_execution.get('op_type')}` {latest_execution.get('payload', {})}")
    else:
        lines.append("- 无")

    lines.extend(["", "## 最近操作", ""])
    if recent_ops:
        for entry in reversed(recent_ops):
            lines.append(f"- `{entry.get('at')}` `{entry.get('op_type')}` {entry.get('payload', {})}")
    else:
        lines.append("- 无")

    lines.extend(["", "## 工程卫生", ""])
    if hygiene_payload is None:
        lines.append("- 尚未生成 tooling-hygiene 产物。")
    else:
        issue_count = int(hygiene_payload.get("issue_count", 0))
        lines.append(f"- issue 数量：`{issue_count}`")
        issues = hygiene_payload.get("issues")
        if isinstance(issues, list) and issues:
            for issue in issues[:5]:
                if isinstance(issue, dict):
                    lines.append(f"- [{issue.get('severity', 'info')}] {issue.get('path')} - {issue.get('message')}")
        elif issue_count == 0:
            lines.append("- 当前未发现异常生成产物或明显工程卫生问题。")

    lines.extend(
        [
            "",
            "## Feature 列表",
            "",
            "| Feature | 阶段 | 风险 | 审批 | gate2 | gate3 | gate4 | gate5 | 缺失产物 | 阻塞项 | 下一步 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )

    for state in states:
        missing = len(state.get("missing_artifacts", [])) if isinstance(state.get("missing_artifacts"), list) else 0
        blockers = len(state.get("blockers", [])) if isinstance(state.get("blockers"), list) else 0
        next_command = str(state.get("next_command", "N/A")).replace("|", "\\|")
        lines.append(
            f"| {state.get('feature_name')} | {state.get('current_stage')} | {state.get('risk_tier')} | "
            f"{state.get('approval_status')} | {state.get('gate2_result')} | {state.get('gate3_result')} | "
            f"{state.get('gate4_result')} | {state.get('gate5_result')} | {missing} | {blockers} | `{next_command}` |"
        )

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default=str(SPECS_DIR),
        help="输出目录，默认写到当前附着项目对应的项目级产物目录",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    states = [inspect_feature_state(feature_dir) for feature_dir in iter_feature_dirs()]
    candidate = choose_candidate(states)
    hygiene_path = output_dir / "tooling-hygiene.json"
    if not hygiene_path.exists():
        hygiene_path = output_dir / "workspace-hygiene.json"
    hygiene_payload = read_json(hygiene_path) if hygiene_path.exists() else None

    payload = {
        "feature_count": len(states),
        "stage_counts": dict(Counter(str(state.get("current_stage", "unknown")) for state in states)),
        "candidate": candidate,
        "latest_execution": read_latest_op(["continue-project-flow", "project-cycle"]),
        "recent_ops": read_recent_ops(10),
        "tooling_hygiene": hygiene_payload,
        "workspace_hygiene": hygiene_payload,
        "features": states,
    }

    json_path = output_dir / "project-console.json"
    md_path = output_dir / "project-console.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(states, candidate, hygiene_payload if isinstance(hygiene_payload, dict) else None), encoding="utf-8")

    print("[OK] project-console 已生成")
    print(f"  - json: {json_path}")
    print(f"  - md:   {md_path}")
    if candidate is not None:
        print(f"  - next: {candidate.get('next_command')}")
    else:
        print("  - next: <none>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
