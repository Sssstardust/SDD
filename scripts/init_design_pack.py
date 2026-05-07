#!/usr/bin/env python3
"""
init_design_pack.py

按 feature-brief.md 中的 capability_tags 初始化 design-pack/ 下的最小文件。
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT / ".spec" / "templates" / "design-pack"


TAG_TO_FILES = {
    "api": ["接口契约.openapi.yaml", "接口文档.md"],
    "db-change": ["数据模型.md", "数据库变更.sql"],
    "idempotent": ["幂等策略.md"],
    "payment": ["支付状态机.md", "对账策略.md"],
    "async": ["异步事件契约.yaml"],
    "external-call": ["外部调用策略.md"],
}

LEVEL_ALLOWED_TAGS = {
    "light": {"api"},
    "standard": {"api", "db-change"},
    "full": set(TAG_TO_FILES.keys()),
}

TEMPLATE_MAP = {
    "接口文档.md": "接口文档.template.md",
    "数据模型.md": "数据模型.template.md",
    "幂等策略.md": "幂等策略.template.md",
    "支付状态机.md": "支付状态机.template.md",
    "对账策略.md": "对账策略.template.md",
    "外部调用策略.md": "外部调用策略.template.md",
}


def extract_yaml_block(text: str) -> str:
    match = re.search(r"```yaml\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return match.group(1) if match else text


def extract_scalar(yaml_text: str, key: str) -> str | None:
    pattern = rf"(?m)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$"
    m = re.search(pattern, yaml_text)
    return m.group(1).strip().strip('"').strip("'") if m else None


def extract_list_items(yaml_text: str, key: str) -> list[str]:
    lines = yaml_text.splitlines()
    items: list[str] = []
    in_block = False
    base_indent = 0
    for line in lines:
        if not in_block:
            if re.match(rf"^\s*{re.escape(key)}\s*:\s*$", line):
                in_block = True
                base_indent = len(line) - len(line.lstrip())
            continue
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= base_indent and not line.lstrip().startswith("- "):
            break
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip().strip('"').strip("'"))
    return items


def render_machine_file(filename: str, feature_name: str) -> str:
    if filename == "接口契约.openapi.yaml":
        return (
            "openapi: 3.0.3\n"
            "info:\n"
            f"  title: {feature_name} API\n"
            "  version: 1.0.0\n"
            "paths: {}\n"
        )
    if filename == "数据库变更.sql":
        return "-- UP\n\n-- TODO: 写入数据库变更脚本\n\n-- DOWN\n\n-- TODO: 写入回滚脚本\n"
    if filename == "异步事件契约.yaml":
        return (
            "event: TODO_EVENT\n"
            "topic: TODO_TOPIC\n"
            "producer: TODO_PRODUCER\n"
            "consumer: TODO_CONSUMER\n"
            "payload:\n"
            "  type: object\n"
            "retry:\n"
            "  max_attempts: 3\n"
            "dlq: TODO_DLQ\n"
        )
    return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_brief", help="feature-brief.md 路径")
    args = parser.parse_args()

    feature_brief = Path(args.feature_brief)
    if not feature_brief.exists():
        print(f"[ERROR] 文件不存在: {feature_brief}")
        return 1

    text = feature_brief.read_text(encoding="utf-8")
    yaml_text = extract_yaml_block(text)
    feature_name = extract_scalar(yaml_text, "feature_name") or "TODO_FEATURE"
    sdd_level = extract_scalar(yaml_text, "sdd_level")
    tags = extract_list_items(yaml_text, "capability_tags")
    if not tags:
        print("[ERROR] capability_tags 为空，无法初始化 design-pack")
        return 1
    if sdd_level:
        normalized_level = sdd_level.lower()
        if normalized_level not in LEVEL_ALLOWED_TAGS:
            print("[ERROR] sdd_level 必须是 light / standard / full")
            return 1
        disallowed_tags = sorted(set(tags) - LEVEL_ALLOWED_TAGS[normalized_level])
        if disallowed_tags:
            print(f"[ERROR] {sdd_level} SDD 不允许 capability_tags: {', '.join(disallowed_tags)}")
            return 1

    feature_dir = feature_brief.parent
    design_pack_dir = feature_dir / "design-pack"
    design_pack_dir.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    for tag in tags:
        for filename in TAG_TO_FILES.get(tag, []):
            target = design_pack_dir / filename
            if target.exists():
                continue
            template_name = TEMPLATE_MAP.get(filename)
            if template_name:
                template = TEMPLATE_DIR / template_name
                if template.exists():
                    target.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
                else:
                    target.write_text(f"# {filename}\n", encoding="utf-8")
            else:
                target.write_text(render_machine_file(filename, feature_name), encoding="utf-8")
            created.append(str(target))

    print("[OK] design-pack 初始化完成")
    print(f"  - feature: {feature_name}")
    print(f"  - tags: {', '.join(tags)}")
    for item in created:
        print(f"  - created: {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
