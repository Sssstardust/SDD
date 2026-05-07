#!/usr/bin/env python3
"""
init_design.py

为 specs/<feature>/ 生成下一版 design-v{N}.md（若不存在）。
"""

from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

from versioning import design_version_number, detect_next_design_path, reports_dir_for_design, resolve_feature_dir


ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "document" / "template" / "design-template.md"


def extract_yaml_blocks(text: str) -> list[str]:
    matches = re.findall(r"```yaml\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return matches if matches else [text]


def extract_scalar(yaml_text: str, key: str) -> str | None:
    m = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", yaml_text)
    if not m:
        return None
    return m.group(1).strip().strip('"').strip("'")


def render_template(feature_brief: Path, design_path: Path) -> str:
    text = feature_brief.read_text(encoding="utf-8")
    yaml_text = "\n".join(extract_yaml_blocks(text))
    feature_name = extract_scalar(yaml_text, "feature_name") or feature_brief.parent.name
    feature_dir_name = feature_brief.parent.name
    version_no = design_version_number(design_path)
    template = TEMPLATE.read_text(encoding="utf-8")
    return (
        template.replace("{{feature_name}}", feature_name)
        .replace("{{feature_dir_name}}", feature_dir_name)
        .replace("{{design_version}}", f"v{version_no}.0")
        .replace("{{date}}", str(date.today()))
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    args = parser.parse_args()

    feature_dir = resolve_feature_dir(args.feature_dir)
    if not feature_dir.exists():
        print(f"[ERROR] feature 目录不存在: {feature_dir}")
        return 1

    feature_brief = feature_dir / "feature-brief.md"
    if not feature_brief.exists():
        print(f"[ERROR] 缺少 feature-brief.md: {feature_brief}")
        return 1

    design_path = detect_next_design_path(feature_dir)
    if not design_path.exists():
        design_path.write_text(render_template(feature_brief, design_path), encoding="utf-8")
        reports_dir = reports_dir_for_design(feature_dir, design_path)
        reports_dir.mkdir(parents=True, exist_ok=True)
        print(f"[OK] 已生成设计文档: {design_path}")
        print(f"  - reports: {reports_dir}")
    else:
        print(f"[OK] 设计文档已存在，跳过生成: {design_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
