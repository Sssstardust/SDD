#!/usr/bin/env python3
"""
bootstrap_feature.py

为 greenfield feature 生成正式的 bootstrap 产物。
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from bootstrap_utils import (
    BOOTSTRAP_REQUIRED_FILES,
    BOOTSTRAP_TEMPLATE_DIR,
    BOOTSTRAP_TEMPLATE_MAP,
    render_bootstrap_file,
    write_scaffold_report,
)
from versioning import resolve_feature_dir


def extract_yaml_blocks(text: str) -> list[str]:
    matches = re.findall(r"```yaml\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return matches if matches else [text]


def extract_scalar(yaml_text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", yaml_text)
    if not match:
        return None
    return match.group(1).strip().strip('"').strip("'")


def read_feature_name(feature_dir: Path) -> str:
    feature_brief = feature_dir / "feature-brief.md"
    if not feature_brief.exists():
        return feature_dir.name

    yaml_text = "\n".join(extract_yaml_blocks(feature_brief.read_text(encoding="utf-8")))
    return extract_scalar(yaml_text, "feature_name") or feature_dir.name


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--force", action="store_true", help="允许覆盖已存在的 bootstrap 产物")
    args = parser.parse_args()

    feature_dir = resolve_feature_dir(args.feature_dir)
    feature_dir.mkdir(parents=True, exist_ok=True)
    feature_name = read_feature_name(feature_dir)

    missing_templates = [name for name in BOOTSTRAP_TEMPLATE_MAP if not (BOOTSTRAP_TEMPLATE_DIR / name).exists()]
    if missing_templates:
        print(f"[ERROR] 缺少 bootstrap 模板: {', '.join(missing_templates)}")
        return 1

    generated_files: list[str] = []
    preserved_files: list[str] = []

    for template_name, output_name in BOOTSTRAP_TEMPLATE_MAP.items():
        template_path = BOOTSTRAP_TEMPLATE_DIR / template_name
        output_path = feature_dir / output_name
        if output_path.exists() and not args.force:
            preserved_files.append(output_name)
            continue

        rendered = render_bootstrap_file(output_name, template_path.read_text(encoding="utf-8"), feature_name)
        output_path.write_text(rendered, encoding="utf-8")
        generated_files.append(output_name)

    report_path = write_scaffold_report(feature_dir, feature_name, generated_files, preserved_files)
    if BOOTSTRAP_REQUIRED_FILES and report_path.name not in generated_files:
        generated_files.append(report_path.name)

    print("[OK] Greenfield bootstrap 初始化完成")
    print(f"  - feature: {feature_name}")
    print(f"  - dir:     {feature_dir}")
    print(f"  - created: {', '.join(generated_files) if generated_files else 'none'}")
    print(f"  - kept:    {', '.join(preserved_files) if preserved_files else 'none'}")
    print(f"  - report:  {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
