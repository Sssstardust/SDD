from __future__ import annotations
import re
from typing import Any
from sdd_core.domain.design_common import safe_slug, unique_preserve, GENERIC_ENTITY_SLUGS

def infer_table_entries(context: dict[str, Any]) -> list[dict[str, Any]]:
    matched_tables = list(context["schema_context"]["matched_tables"])
    structured_prd = context["structured_prd"]
    entities = preferred_entities(context)
    requirements = structured_prd.get("requirements", []) or []
    req_ids = [str(item.get("req_id") or "REQ-001") for item in requirements if isinstance(item, dict)]
    req_ids_text = ", ".join(req_ids[:3]) or "REQ-001"

    entries: list[dict[str, Any]] = []
    if matched_tables:
        for index, table in enumerate(matched_tables, start=1):
            table_name = str(table.get("table_name") or f"t_{context['feature_slug'].replace('-', '_')}_{index}")
            columns = [str(col) for col in table.get("columns", []) if isinstance(col, str)] or ["id", "status", "updated_at"]
            indexed_columns = [str(col) for col in table.get("indexed_columns", []) if isinstance(col, str)]
            entity_name = entities[index - 1] if index - 1 < len(entities) else context["feature_pascal"] + str(index)
            entries.append(
                {
                    "entity": entity_name,
                    "table_name": table_name,
                    "existing_table": True,
                    "purpose": f"支撑 {entity_name} 相关需求",
                    "req_ids": req_ids_text,
                    "columns": columns,
                    "indexed_columns": indexed_columns,
                    "sql_columns": [str(col) for col in table.get("sql_columns", []) if isinstance(col, str)],
                }
            )
        return entries

    used_table_names: set[str] = set()
    for index, entity_name in enumerate(entities[:3], start=1):
        table_name = f"t_{context['feature_slug'].replace('-', '_')}_{safe_slug(entity_name, f'entity-{index}').replace('-', '_')}"
        if table_name in used_table_names:
            table_name = f"{table_name}_{index}"
        used_table_names.add(table_name)
        entries.append(
            {
                "entity": entity_name,
                "table_name": table_name,
                "existing_table": False,
                "purpose": f"新领域模式下承载 {entity_name} 数据",
                "req_ids": req_ids_text,
                "columns": ["id", "status", "created_at", "updated_at"],
                "indexed_columns": ["status"],
                "sql_columns": ["status"],
            }
        )
    return entries

def infer_column_type(column: str) -> str:
    if column.endswith("_time") or column.endswith("_at"):
        return "datetime"
    if column.endswith("_id") or column == "id":
        return "varchar(64)"
    if column in {"status", "type"}:
        return "varchar(32)"
    return "varchar(128)"

def preferred_entities(context: dict[str, Any]) -> list[str]:
    structured_prd = context["structured_prd"]
    raw_entities: list[str] = []
    for item in structured_prd.get("entities", []) or []:
        if isinstance(item, dict):
            name = str(item.get("name") or "")
        else:
            name = str(item)
        if name:
            raw_entities.append(name)
    deduped = unique_preserve(raw_entities)
    ascii_entities = [
        name
        for name in deduped
        if re.search(r"[A-Za-z]", name) and safe_slug(name, "") not in GENERIC_ENTITY_SLUGS
    ]
    if ascii_entities:
        return ascii_entities
    filtered = [name for name in deduped if safe_slug(name, "") not in GENERIC_ENTITY_SLUGS]
    return filtered or [context["feature_pascal"]]

