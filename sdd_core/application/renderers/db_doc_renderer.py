from __future__ import annotations
from typing import Any
from sdd_core.domain.design_common import safe_slug, unique_preserve, feature_req_ids
from sdd_core.domain.db_schema_inferer import infer_table_entries, infer_column_type

def render_data_model(context: dict[str, Any], design_version: str) -> str:
    requirements = context["structured_prd"].get("requirements", []) or []
    req_ids_text = feature_req_ids(requirements)
    table_entries = infer_table_entries(context)
    mapping_rows = "\n".join(
        f"| {entry['entity']} | {entry['table_name']} | {entry['purpose']} | {entry['req_ids']} |"
        for entry in table_entries
    )
    unique_columns = unique_preserve([column for entry in table_entries for column in entry["columns"]])
    field_rows = "\n".join(
        f"| {column} | {infer_column_type(column)} | 支撑 {context['feature_name']} 的 {column} 信息 | {'是' if column in {'id', 'status'} else '否'} | {'无' if column != 'status' else 'DRAFT'} |  |"
        for column in unique_columns[:10]
    )
    index_rows: list[str] = []
    for entry in table_entries:
        if entry["indexed_columns"]:
            columns_text = ",".join(entry["indexed_columns"])
            index_rows.append(
                f"| idx_{safe_slug(entry['entity'], 'entity').replace('-', '_')} | {columns_text} | 普通索引 | 支撑查询与状态过滤 |"
            )
    if not index_rows:
        index_rows.append("| idx_status | status | 普通索引 | 支撑状态过滤 |")
    return f"""# 数据模型

## 1. 元信息

- feature_name: {context['feature_name']}
- design_version: {design_version}
- req_ids: {req_ids_text}

## 2. 实体与表映射

| 实体 | 表名 | 用途 | 对应 REQ-ID |
| --- | --- | --- | --- |
{mapping_rows}

## 3. 字段清单

### 3.1 主表字段

| 字段名 | 类型 | 含义 | 是否必填 | 默认值 | 备注 |
| --- | --- | --- | --- | --- | --- |
{field_rows}

### 3.2 索引设计

| 索引名 | 字段 | 类型 | 目的 |
| --- | --- | --- | --- |
{chr(10).join(index_rows)}

## 4. 关系与约束

- 主外键关系：由主实体到扩展实体按业务关系建立
- 唯一约束：关键业务主键与状态组合需保证一致性
- 幂等约束：{"由业务幂等键保证" if 'idempotent' in context['capability_tags'] else "当前未额外声明幂等约束"}

## 5. 变更影响分析

- 对现有表的影响：{"可能涉及存量表字段/索引调整" if context['schema_context']['matched_tables'] else "当前处于待确认或新领域模式"}
- 对历史数据的影响：需评估历史数据回填与兼容策略
- 对查询性能的影响：索引设计需支撑主查询路径

## 6. 人工审阅关注点

- 字段语义是否清晰：需在评审中确认
- 索引是否过多或不足：需结合真实读写路径确认
- 是否存在模型冗余：需结合领域边界确认
"""

def render_sql(context: dict[str, Any]) -> str:
    entries = infer_table_entries(context)
    lines = ["-- UP", ""]
    for entry in entries:
        table_name = entry["table_name"]
        sql_columns = entry["sql_columns"] or entry["columns"][:3]
        if entry.get("existing_table", False):
            for column in sql_columns:
                lines.append(f"ALTER TABLE {table_name} ADD COLUMN {column} {infer_column_type(column)};")
            for index_columns in [entry["indexed_columns"]] if entry["indexed_columns"] else []:
                columns_text = ",".join(index_columns)
                index_name = f"idx_{safe_slug(entry['entity'], 'entity').replace('-', '_')}"
                lines.append(f"CREATE INDEX {index_name} ON {table_name} ({columns_text});")
        else:
            lines.append(f"CREATE TABLE {table_name} (")
            lines.append("  id varchar(64) primary key,")
            lines.append("  status varchar(32),")
            lines.append("  created_at datetime")
            lines.append(");")
    lines.extend(["", "-- DOWN", ""])
    for entry in reversed(entries):
        table_name = entry["table_name"]
        if entry.get("existing_table", False):
            lines.append(f"-- ROLLBACK for {table_name}")
            for column in reversed(entry["sql_columns"] or entry["columns"][:3]):
                lines.append(f"ALTER TABLE {table_name} DROP COLUMN {column};")
        else:
            lines.append(f"DROP TABLE {table_name};")
    return "\n".join(lines) + "\n"

