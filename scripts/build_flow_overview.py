#!/usr/bin/env python3
"""
build_flow_overview.py

生成项目级的多 feature 主流程状态总览。
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from flow_state import inspect_feature_state
from project_artifact_paths import get_active_project_artifacts_dir
from versioning import iter_feature_dirs


def render_markdown(states: list[dict[str, object]]) -> str:
    stage_counter = Counter(str(state.get("current_stage", "unknown")) for state in states)
    lines = [
        "# Project Flow Overview",
        "",
        f"- feature 数量：`{len(states)}`",
        "",
        "## 阶段分布",
        "",
    ]

    for stage, count in sorted(stage_counter.items()):
        lines.append(f"- `{stage}`: {count}")

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
        feature_name = str(state.get("feature_name", "N/A"))
        stage = str(state.get("current_stage", "N/A"))
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
            f"| {feature_name} | {stage} | {risk_tier} | {approval} | {gate2} | {gate3} | {gate4} | {gate5} | {missing} | {blockers} | `{next_command}` |"
        )

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default=str(get_active_project_artifacts_dir(create=True)),
        help="总览输出目录，默认写到当前附着项目对应的项目级产物目录",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    feature_dirs = iter_feature_dirs()
    states = [inspect_feature_state(feature_dir) for feature_dir in feature_dirs]

    payload = {
        "feature_count": len(states),
        "features": states,
    }

    json_path = output_dir / "flow-overview.json"
    md_path = output_dir / "flow-overview.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(states), encoding="utf-8")

    print("[OK] flow-overview 已生成")
    print(f"  - json: {json_path}")
    print(f"  - md:   {md_path}")
    print(f"  - features: {len(states)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
