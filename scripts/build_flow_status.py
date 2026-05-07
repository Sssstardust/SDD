#!/usr/bin/env python3
"""
build_flow_status.py

生成 feature 当前主流程状态的 JSON 与 Markdown 概览。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from flow_state import inspect_feature_state
from versioning import resolve_feature_dir


def render_markdown(state: dict[str, object]) -> str:
    lines = [
        f"# Flow Status：{state.get('feature_name')}",
        "",
        f"- 当前阶段：`{state.get('current_stage')}`",
        f"- 风险级别：`{state.get('risk_tier')}`",
        f"- 设计版本：`{state.get('design_version', 'N/A')}`",
        f"- 审批状态：`{state.get('approval_status', 'N/A')}`",
        "",
        "## 门禁结果",
        "",
        f"- `gate2`: `{state.get('gate2_result', 'N/A')}`",
        f"- `gate3`: `{state.get('gate3_result', 'N/A')}`",
        f"- `gate4`: `{state.get('gate4_result', 'N/A')}`",
        f"- `gate5`: `{state.get('gate5_result', 'N/A')}`",
        f"- `release_gate`: `{state.get('release_gate_result', 'N/A')}`",
        "",
        "## 缺失产物",
        "",
    ]

    missing = state.get("missing_artifacts") if isinstance(state.get("missing_artifacts"), list) else []
    if missing:
        lines.extend([f"- `{item}`" for item in missing])
    else:
        lines.append("- 无")

    lines.extend(
        [
            "",
            "## 阻塞项",
            "",
        ]
    )
    blockers = state.get("blockers") if isinstance(state.get("blockers"), list) else []
    if blockers:
        lines.extend([f"- {item}" for item in blockers])
    else:
        lines.append("- 无")

    lines.extend(
        [
            "",
        "## 下一步建议",
        "",
        f"- 原因：{state.get('reason', '无')}",
        f"- 命令：`{state.get('next_command', 'N/A')}`",
        "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    args = parser.parse_args()

    feature_dir = resolve_feature_dir(args.feature_dir)
    if not feature_dir.exists():
        print(f"[ERROR] feature 目录不存在: {feature_dir}")
        return 1

    state = inspect_feature_state(feature_dir)
    json_path = feature_dir / "flow-status.json"
    md_path = feature_dir / "flow-status.md"

    json_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(state), encoding="utf-8")

    print("[OK] flow-status 已生成")
    print(f"  - json: {json_path}")
    print(f"  - md:   {md_path}")
    print(f"  - next: {state.get('next_command')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
