#!/usr/bin/env python3
"""
build_project_next.py

基于项目级 feature 状态，挑选当前最值得推进的 feature。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from flow_state import inspect_feature_state
from ops_log import read_latest_op
from project_artifact_paths import get_active_project_artifacts_dir
from versioning import get_primary_design_root, iter_feature_dirs

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

def choose_candidate(states: list[dict[str, object]]) -> dict[str, object] | None:
    actionable = [
        state
        for state in states
        if str(state.get("current_stage")) != "release-ready"
        and str(state.get("next_command", "")).strip()
    ]
    if not actionable:
        return None

    def sort_key(state: dict[str, object]) -> tuple[int, int, str]:
        stage = str(state.get("current_stage", "unknown"))
        priority = STAGE_PRIORITY.get(stage, 99)
        risk = 0 if str(state.get("risk_tier")) == "high" else 1
        feature_name = str(state.get("feature_name", ""))
        return (priority, risk, feature_name)

    return sorted(actionable, key=sort_key)[0]


def render_markdown(states: list[dict[str, object]], candidate: dict[str, object] | None) -> str:
    lines = [
        "# Project Next Action",
        "",
    ]

    latest_execution = read_latest_op(["continue-project-flow", "project-cycle"])
    lines.extend(
        [
            "## 最近推进结果",
            "",
        ]
    )
    if latest_execution:
        lines.append(
            f"- `{latest_execution.get('at')}` `{latest_execution.get('op_type')}` {latest_execution.get('payload', {})}"
        )
    else:
        lines.append("- 无")

    if candidate is None:
        lines.extend(
            [
                "",
                "- 当前没有需要自动推进的 feature。",
                "- 所有正式 feature 都已处于 `release-ready`，或缺少可执行的下一步命令。",
                "",
            ]
        )
    else:
        lines.extend(
            [
                f"- 推荐 feature：`{candidate.get('feature_name')}`",
                f"- 当前阶段：`{candidate.get('current_stage')}`",
                f"- 风险级别：`{candidate.get('risk_tier')}`",
                f"- 原因：{candidate.get('reason')}",
                f"- 下一步命令：`{candidate.get('next_command')}`",
                "",
            ]
        )

    lines.extend(
        [
            "## 候选列表",
            "",
            "| Feature | 阶段 | 风险 | 缺失产物 | 阻塞项 | 下一步 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for state in states:
        feature_name = str(state.get("feature_name", "N/A"))
        stage = str(state.get("current_stage", "N/A"))
        risk = str(state.get("risk_tier", "N/A"))
        missing = len(state.get("missing_artifacts", [])) if isinstance(state.get("missing_artifacts"), list) else 0
        blockers = len(state.get("blockers", [])) if isinstance(state.get("blockers"), list) else 0
        next_command = str(state.get("next_command", "N/A")).replace("|", "\\|")
        lines.append(f"| {feature_name} | {stage} | {risk} | {missing} | {blockers} | `{next_command}` |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default=str(get_active_project_artifacts_dir(create=True)),
        help="输出目录，默认写到当前附着项目对应的项目级产物目录",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    states = [inspect_feature_state(feature_dir) for feature_dir in iter_feature_dirs()]
    candidate = choose_candidate(states)

    payload = {
        "feature_count": len(states),
        "candidate": candidate,
        "latest_execution": read_latest_op(["continue-project-flow", "project-cycle"]),
        "features": states,
    }

    json_path = output_dir / "project-next.json"
    md_path = output_dir / "project-next.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(states, candidate), encoding="utf-8")

    print("[OK] project-next 已生成")
    print(f"  - json: {json_path}")
    print(f"  - md:   {md_path}")
    if candidate is not None:
        print(f"  - next: {candidate.get('next_command')}")
    else:
        print("  - next: <none>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
