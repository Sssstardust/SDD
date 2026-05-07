#!/usr/bin/env python3
"""
check_design_pack.py

按 feature-brief.md 中的 capability_tags 对 design-pack 做校验：
- 文件存在
- 文件非空
- 机器文件的最小 schema / 规则检查
- 人工审阅 Markdown 文件的最小章节 / 表格 / 关键词检查
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from json_io import read_json


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
FULL_ONLY_TAGS = {"idempotent", "payment", "async", "external-call"}

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / ".spec" / "schemas" / "design-pack"
MARKDOWN_RULE_MAP = {
    "接口文档.md": "接口文档.rules.json",
    "数据模型.md": "数据模型.rules.json",
    "幂等策略.md": "幂等策略.rules.json",
    "支付状态机.md": "支付状态机.rules.json",
    "对账策略.md": "对账策略.rules.json",
}


def extract_yaml_block(text: str) -> str:
    match = re.search(r"```yaml\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return match.group(1) if match else text


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


def extract_scalar(yaml_text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", yaml_text)
    if not match:
        return None
    return match.group(1).strip().strip('"').strip("'")


def validate_sdd_level_rules(
    *,
    sdd_level: str | None,
    risk_tier: str | None,
    tags: list[str],
    errors: list[str],
) -> None:
    if not sdd_level:
        return

    normalized_level = sdd_level.lower()
    if normalized_level not in LEVEL_ALLOWED_TAGS:
        errors.append("sdd_level 必须是 light / standard / full")
        return

    disallowed_tags = sorted(set(tags) - LEVEL_ALLOWED_TAGS[normalized_level])
    if disallowed_tags:
        label = {"light": "轻量 SDD", "standard": "标准 SDD", "full": "完整 SDD"}[normalized_level]
        errors.append(f"{label} 不允许 capability_tags: {', '.join(disallowed_tags)}")

    full_only_tags = sorted(set(tags) & FULL_ONLY_TAGS)
    if full_only_tags and normalized_level != "full":
        errors.append(f"capability_tags {', '.join(full_only_tags)} 必须使用完整 SDD")

    if (risk_tier or "").lower() == "high" and normalized_level != "full":
        errors.append("高风险 feature 必须使用完整 SDD")


def load_schema(name: str) -> dict:
    return read_json(SCHEMA_DIR / name)  # type: ignore[return-value]


def validate_by_schema(value: object, schema: dict, label: str, errors: list[str]) -> None:
    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(value, dict):
            errors.append(f"{label} 不是对象")
            return
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{label} 缺少字段: {key}")
        for key, child_schema in schema.get("properties", {}).items():
            if key in value:
                validate_by_schema(value[key], child_schema, f"{label}.{key}", errors)
    elif schema_type == "string":
        if not isinstance(value, str):
            errors.append(f"{label} 不是字符串")


def parse_simple_yaml(text: str) -> dict:
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if ":" not in raw_line:
            continue

        indent = len(raw_line) - len(raw_line.lstrip())
        key, value = raw_line.strip().split(":", 1)
        value = value.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()
        current = stack[-1][1]

        if value == "":
            child: dict = {}
            current[key] = child
            stack.append((indent, child))
        else:
            current[key] = value

    return root


def validate_openapi_machine_file(path: Path, content: str, errors: list[str]) -> None:
    data = parse_simple_yaml(content)
    validate_by_schema(data, load_schema("openapi.schema.json"), path.name, errors)

    operations = extract_openapi_operations(content)
    path_names = sorted({operation["path"] for operation in operations})
    if not operations:
        errors.append(f"{path.name} 至少需要一个 paths 条目")

    operation_ids: list[str] = []
    for operation in operations:
        label = f"{operation['method'].upper()} {operation['path']}"
        block = str(operation["block"])
        operation_id_match = re.search(r"(?m)^\s{6}operationId:\s*(\S+)\s*$", block)
        if not operation_id_match:
            errors.append(f"{path.name} {label} 缺少 operationId")
        else:
            operation_ids.append(operation_id_match.group(1))

        response_block_match = re.search(r"(?m)^\s{6}responses:\s*$", block)
        if not response_block_match:
            errors.append(f"{path.name} {label} 缺少 responses")
        elif not re.search(r"(?m)^\s{8}['\"]?\d{3}['\"]?\s*:\s*$", block):
            errors.append(f"{path.name} {label} responses 至少需要一个 HTTP 状态码")

        path_params = re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", str(operation["path"]))
        for param_name in path_params:
            param_pattern = (
                rf"(?ms)^\s{{8}}-\s*name:\s*{re.escape(param_name)}\s*$"
                rf".*?^\s{{10}}in:\s*path\s*$"
            )
            if not re.search(param_pattern, block):
                errors.append(f"{path.name} {label} 路径参数 {{{param_name}}} 未声明为 in: path")

    duplicate_operation_ids = sorted({item for item in operation_ids if operation_ids.count(item) > 1})
    if duplicate_operation_ids:
        errors.append(f"{path.name} operationId 重复: {', '.join(duplicate_operation_ids)}")


def extract_openapi_operations(content: str) -> list[dict[str, str]]:
    operations: list[dict[str, str]] = []
    lines = content.splitlines()
    current_path: str | None = None
    current_method: str | None = None
    current_block: list[str] = []

    def flush() -> None:
        if current_path and current_method:
            operations.append({"path": current_path, "method": current_method, "block": "\n".join(current_block)})

    for line in lines:
        path_match = re.match(r"^\s{2}(/[^\s:]+)\s*:\s*$", line)
        method_match = re.match(r"^\s{4}(get|post|put|delete|patch|head|options)\s*:\s*$", line, re.IGNORECASE)
        if path_match:
            flush()
            current_path = path_match.group(1)
            current_method = None
            current_block = []
            continue
        if method_match and current_path:
            flush()
            current_method = method_match.group(1).lower()
            current_block = [line]
            continue
        if current_method:
            current_block.append(line)

    flush()
    return operations


def validate_async_machine_file(path: Path, content: str, errors: list[str]) -> None:
    data = parse_simple_yaml(content)
    validate_by_schema(data, load_schema("async-event.schema.json"), path.name, errors)
    if "retry:" in content and "max_attempts:" not in content:
        errors.append(f"{path.name} 缺少 retry.max_attempts")


def validate_sql_machine_file(path: Path, content: str, errors: list[str]) -> None:
    upper = content.upper()
    if "-- UP" not in upper:
        errors.append(f"{path.name} 缺少 `-- UP`")
    if "-- DOWN" not in upper and "-- ROLLBACK" not in upper:
        errors.append(f"{path.name} 缺少 `-- DOWN` 或 `-- ROLLBACK`")
    if "ALTER TABLE" not in upper and "CREATE TABLE" not in upper:
        errors.append(f"{path.name} 至少需要包含 ALTER TABLE 或 CREATE TABLE")
    up_block, down_block = split_sql_migration_blocks(content)
    if "-- UP" in upper and not has_migration_statement(up_block):
        errors.append(f"{path.name} `-- UP` 后缺少实际迁移语句")
    if ("-- DOWN" in upper or "-- ROLLBACK" in upper) and not has_rollback_statement(down_block):
        errors.append(f"{path.name} 回滚段缺少实际回滚语句")
    created_tables = sorted(set(re.findall(r"CREATE\s+TABLE\s+(t_[a-zA-Z0-9_]+)", up_block, re.IGNORECASE)))
    for table_name in created_tables:
        if not re.search(rf"DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?{re.escape(table_name)}\b", down_block, re.IGNORECASE):
            errors.append(f"{path.name} CREATE TABLE {table_name} 缺少对应 DROP TABLE 回滚")
    added_columns = re.findall(
        r"ALTER\s+TABLE\s+(t_[a-zA-Z0-9_]+)\s+ADD\s+COLUMN\s+([a-z_][a-z0-9_]*)",
        up_block,
        re.IGNORECASE,
    )
    for table_name, column_name in added_columns:
        rollback_pattern = rf"ALTER\s+TABLE\s+{re.escape(table_name)}\s+DROP\s+COLUMN\s+{re.escape(column_name)}\b"
        if not re.search(rollback_pattern, down_block, re.IGNORECASE):
            errors.append(f"{path.name} ADD COLUMN {table_name}.{column_name} 缺少对应 DROP COLUMN 回滚")


def split_sql_migration_blocks(content: str) -> tuple[str, str]:
    up_match = re.search(r"(?is)--\s*UP\b(.*?)(?=--\s*(?:DOWN|ROLLBACK)\b|\Z)", content)
    down_match = re.search(r"(?is)--\s*(?:DOWN|ROLLBACK)\b(.*)\Z", content)
    return (up_match.group(1) if up_match else "", down_match.group(1) if down_match else "")


def strip_sql_comments(content: str) -> str:
    content = re.sub(r"--.*?$", "", content, flags=re.MULTILINE)
    return re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)


def has_migration_statement(content: str) -> bool:
    cleaned = strip_sql_comments(content).upper()
    return bool(re.search(r"\b(CREATE|ALTER)\s+TABLE\b", cleaned))


def has_rollback_statement(content: str) -> bool:
    cleaned = strip_sql_comments(content).upper()
    return bool(re.search(r"\b(DROP\s+TABLE|ALTER\s+TABLE\s+\S+\s+DROP\s+COLUMN)\b", cleaned))


def section_block(text: str, anchor: str) -> str | None:
    pattern = rf"(?ms)^{re.escape(anchor)}\s*$.*?(?=^##\s+\d+\.|^###\s+\d+\.\d+|\Z)"
    match = re.search(pattern, text)
    return match.group(0) if match else None


def count_table_rows(block: str) -> int:
    rows = [line for line in block.splitlines() if line.strip().startswith("|")]
    return max(len(rows) - 2, 0)


def validate_interface_doc_structure(path: Path, content: str, errors: list[str]) -> bool:
    if path.name != "接口文档.md":
        return False

    base_headings = [
        "## 1. 元信息",
        "## 2. 接口清单",
        "## 3. 业务说明",
    ]
    for heading in base_headings:
        if heading not in content:
            errors.append(f"{path.name} 缺少必要章节: {heading}")

    has_legacy_layout = all(
        heading in content
        for heading in [
            "## 4. 请求说明",
            "## 5. 响应说明",
            "## 6. 错误码说明",
            "## 7. 依赖与时序说明",
            "## 8. 人工审阅关注点",
        ]
    )
    has_chaptered_layout = all(
        heading in content
        for heading in [
            "## 4. 接口详情",
            "## 5. 错误码说明",
            "## 6. 依赖与时序说明",
            "## 7. 人工审阅关注点",
        ]
    )

    if not has_legacy_layout and not has_chaptered_layout:
        errors.append(f"{path.name} 缺少可识别的接口文档结构，需满足旧版总表或新版按接口章节格式")
        return True

    summary_block = section_block(content, "## 2. 接口清单")
    if not summary_block or count_table_rows(summary_block) < 1:
        errors.append(f"{path.name} 在 ## 2. 接口清单 中的表格条数不足")

    if has_legacy_layout:
        legacy_anchors = [
            "## 4. 请求说明",
            "## 5. 响应说明",
            "## 6. 错误码说明",
        ]
        for anchor in legacy_anchors:
            block = section_block(content, anchor)
            if not block:
                errors.append(f"{path.name} 缺少表格所在章节: {anchor}")
                continue
            if count_table_rows(block) < 1:
                errors.append(f"{path.name} 在 {anchor} 中的表格条数不足")
        return True

    interface_sections = re.findall(r"(?ms)^###\s+4\.\d+\s+.+?(?=^###\s+4\.\d+\s+|^##\s+5\.|\Z)", content)
    if not interface_sections:
        errors.append(f"{path.name} 在 ## 4. 接口详情 下缺少按接口分节内容")
        return True

    for block in interface_sections:
        if "#### 请求说明" not in block:
            errors.append(f"{path.name} 存在接口分节缺少请求说明")
        if "#### 响应说明" not in block:
            errors.append(f"{path.name} 存在接口分节缺少响应说明")
        if count_table_rows(block) < 2:
            errors.append(f"{path.name} 存在接口分节表格内容不足")

    error_block = section_block(content, "## 5. 错误码说明")
    if not error_block or count_table_rows(error_block) < 1:
        errors.append(f"{path.name} 在 ## 5. 错误码说明 中的表格条数不足")

    return True


def validate_markdown_rule_file(path: Path, content: str, rule_name: str, errors: list[str]) -> None:
    if validate_interface_doc_structure(path, content, errors):
        return

    rules = load_schema(rule_name)

    for heading in rules.get("required_headings", []):
        if heading not in content:
            errors.append(f"{path.name} 缺少必要章节: {heading}")

    for keyword in rules.get("required_keywords", []):
        if keyword not in content:
            errors.append(f"{path.name} 缺少关键语义: {keyword}")

    for table_rule in rules.get("table_checks", []):
        anchor = table_rule.get("anchor")
        min_rows = int(table_rule.get("min_rows", 1))
        if not isinstance(anchor, str):
            continue
        block = section_block(content, anchor)
        if not block:
            errors.append(f"{path.name} 缺少表格所在章节: {anchor}")
            continue
        if count_table_rows(block) < min_rows:
            errors.append(f"{path.name} 在 {anchor} 中的表格条数不足")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser()
    parser.add_argument("feature_brief", help="feature-brief.md 路径")
    args = parser.parse_args()

    feature_brief = Path(args.feature_brief)
    if not feature_brief.exists():
        print(f"[ERROR] 文件不存在: {feature_brief}")
        return 1

    yaml_text = extract_yaml_block(feature_brief.read_text(encoding="utf-8"))
    tags = extract_list_items(yaml_text, "capability_tags")
    sdd_level = extract_scalar(yaml_text, "sdd_level")
    risk_tier = extract_scalar(yaml_text, "risk_tier")
    feature_dir = feature_brief.parent
    design_pack_dir = feature_dir / "design-pack"

    errors: list[str] = []
    checks: list[str] = []

    validate_sdd_level_rules(sdd_level=sdd_level, risk_tier=risk_tier, tags=tags, errors=errors)

    for tag in tags:
        for filename in TAG_TO_FILES.get(tag, []):
            path = design_pack_dir / filename
            if not path.exists():
                errors.append(f"缺少 design-pack 文件: {filename}")
                continue

            content = path.read_text(encoding="utf-8").strip()
            if not content:
                errors.append(f"design-pack 文件为空: {filename}")
                continue

            if filename == "接口契约.openapi.yaml":
                validate_openapi_machine_file(path, content, errors)
            elif filename == "数据库变更.sql":
                validate_sql_machine_file(path, content, errors)
            elif filename == "异步事件契约.yaml":
                validate_async_machine_file(path, content, errors)
            elif filename in MARKDOWN_RULE_MAP:
                validate_markdown_rule_file(path, content, MARKDOWN_RULE_MAP[filename], errors)

            checks.append(filename)

    if errors:
        print("[FAIL] design-pack 校验失败")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("[OK] design-pack 校验通过")
    print(f"  - files: {', '.join(checks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
