#!/usr/bin/env python3
"""
Shared extractors for SDD baseline resources.
"""

from __future__ import annotations

import re
from pathlib import Path


def extract_paths_from_openapi(path: Path) -> list[str]:
    if not path.exists():
        return []
    paths: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = re.match(r"^\s{0,4}(/[A-Za-z0-9_./{}:-]+)\s*:\s*$", line)
        if match:
            paths.add(match.group(1))
    return sorted(paths)


def extract_operations_from_openapi(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    operations: list[dict[str, str]] = []
    current_path: str | None = None
    current_method: str | None = None
    path_indent = 0
    method_indent = 0
    methods = {"get", "post", "put", "delete", "patch", "head", "options", "trace"}
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()
        path_match = re.match(r"^(/[A-Za-z0-9_./{}:-]+)\s*:\s*$", stripped)
        if path_match:
            current_path = path_match.group(1)
            current_method = None
            path_indent = indent
            continue
        if current_path and indent <= path_indent:
            current_path = None
            current_method = None

        method_match = re.match(r"^([a-zA-Z]+)\s*:\s*$", stripped)
        if current_path and method_match and method_match.group(1).lower() in methods:
            current_method = method_match.group(1).upper()
            method_indent = indent
            operations.append({"path": current_path, "method": current_method})
            continue
        if current_method and indent <= method_indent:
            current_method = None

        operation_match = re.match(r"^operationId\s*:\s*['\"]?([^'\"]+)['\"]?\s*$", stripped)
        if current_path and current_method and operation_match and operations:
            operations[-1]["operation_id"] = operation_match.group(1).strip()
    return operations


def extract_tables_from_data_model(path: Path) -> list[str]:
    if not path.exists():
        return []
    tables: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        for table_name in re.findall(r"\bt_[a-zA-Z0-9_]+\b", line):
            tables.add(table_name)
    return sorted(tables)


def extract_table_fields_from_data_model(path: Path) -> dict[str, list[str]]:
    field_specs = extract_table_field_specs_from_data_model(path)
    if field_specs:
        return {table: sorted(fields) for table, fields in field_specs.items()}
    return _extract_table_fields_from_data_model_legacy(path)


def _extract_table_fields_from_data_model_legacy(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="ignore")
    tables = extract_tables_from_data_model(path)
    fields_by_table: dict[str, set[str]] = {table: set() for table in tables}

    for table_name, column_name in re.findall(
        r"\b(t_[a-zA-Z0-9_]+)\.([a-z_][a-z0-9_]*)\b",
        text,
        re.IGNORECASE,
    ):
        fields_by_table.setdefault(table_name, set()).add(column_name)

    current_table: str | None = tables[0] if len(tables) == 1 else None
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells or cells[0] in {"字段名", "---"}:
            continue

        table_cells = [cell for cell in cells if re.fullmatch(r"t_[a-zA-Z0-9_]+", cell)]
        if table_cells:
            current_table = table_cells[0]

        field_name = cells[0]
        if "." in field_name:
            table_part, field_part = field_name.split(".", 1)
            if re.fullmatch(r"t_[a-zA-Z0-9_]+", table_part) and re.fullmatch(r"[a-z_][a-z0-9_]*", field_part):
                fields_by_table.setdefault(table_part, set()).add(field_part)
            continue

        if current_table and re.fullmatch(r"[a-z_][a-z0-9_]*", field_name) and not field_name.startswith("t_"):
            fields_by_table.setdefault(current_table, set()).add(field_name)

    return {table: sorted(fields) for table, fields in sorted(fields_by_table.items()) if fields}


def normalize_markdown_header(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().lower())


def find_header_index(headers: list[str], candidates: set[str]) -> int | None:
    normalized = [normalize_markdown_header(item) for item in headers]
    for index, header in enumerate(normalized):
        if header in candidates:
            return index
    for index, header in enumerate(normalized):
        if any(candidate in header for candidate in candidates):
            return index
    return None


def parse_nullable_value(header: str, value: str) -> bool | None:
    header_norm = normalize_markdown_header(header)
    value_norm = normalize_markdown_header(value)
    if not value_norm:
        return None
    if "必填" in header_norm or "required" in header_norm:
        if value_norm in {"是", "yes", "true", "y", "required", "必填"}:
            return False
        if value_norm in {"否", "no", "false", "n", "optional", "可选"}:
            return True
    if "nullable" in header_norm or "可空" in header_norm or "为空" in header_norm or "null" in header_norm:
        if value_norm in {"是", "yes", "true", "y", "nullable", "可空", "允许", "允许为空"}:
            return True
        if value_norm in {"否", "no", "false", "n", "notnull", "notnull", "非空", "不允许", "不允许为空"}:
            return False
    if any(token in value_norm for token in ["notnull", "非空", "必填", "required", "not-null"]):
        return False
    if any(token in value_norm for token in ["nullable", "可空", "允许为空", "optional"]):
        return True
    return None


def extract_table_field_specs_from_data_model(path: Path) -> dict[str, dict[str, dict[str, object]]]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="ignore")
    tables = extract_tables_from_data_model(path)
    specs_by_table: dict[str, dict[str, dict[str, object]]] = {table: {} for table in tables}

    for table_name, column_name in re.findall(
        r"\b(t_[a-zA-Z0-9_]+)\.([a-z_][a-z0-9_]*)\b",
        text,
        re.IGNORECASE,
    ):
        specs_by_table.setdefault(table_name, {}).setdefault(column_name, {})

    current_table: str | None = tables[0] if len(tables) == 1 else None
    headers: list[str] = []
    field_index: int | None = None
    type_index: int | None = None
    nullable_index: int | None = None

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells:
            continue
        if all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            continue

        normalized_cells = [normalize_markdown_header(cell) for cell in cells]
        if any(cell in {"字段名", "字段", "列名", "column", "name"} for cell in normalized_cells):
            headers = cells
            field_index = find_header_index(headers, {"字段名", "字段", "列名", "column", "name"})
            type_index = find_header_index(headers, {"类型", "字段类型", "数据类型", "type", "datatype"})
            nullable_index = find_header_index(headers, {"nullable", "是否为空", "可空", "是否可空", "是否必填", "必填", "required", "notnull"})
            continue

        table_cells = [cell for cell in cells if re.fullmatch(r"t_[a-zA-Z0-9_]+", cell)]
        if table_cells:
            current_table = table_cells[0]

        if field_index is None or field_index >= len(cells):
            continue

        field_name = cells[field_index]
        table_name = current_table
        if "." in field_name:
            table_part, field_part = field_name.split(".", 1)
            if re.fullmatch(r"t_[a-zA-Z0-9_]+", table_part) and re.fullmatch(r"[a-z_][a-z0-9_]*", field_part):
                table_name = table_part
                field_name = field_part
        if not table_name or not re.fullmatch(r"[a-z_][a-z0-9_]*", field_name) or field_name.startswith("t_"):
            continue

        field_spec = specs_by_table.setdefault(table_name, {}).setdefault(field_name, {})
        if type_index is not None and type_index < len(cells) and cells[type_index]:
            field_spec["type"] = cells[type_index]
        if nullable_index is not None and nullable_index < len(cells):
            nullable = parse_nullable_value(headers[nullable_index] if nullable_index < len(headers) else "", cells[nullable_index])
            if nullable is not None:
                field_spec["nullable"] = nullable

    return {table: fields for table, fields in sorted(specs_by_table.items()) if fields}


def extract_created_tables(sql_path: Path) -> set[str]:
    if not sql_path.exists():
        return set()
    text = sql_path.read_text(encoding="utf-8", errors="ignore")
    return {match.lower() for match in re.findall(r"(?i)\bCREATE\s+TABLE\s+(t_[a-zA-Z0-9_]+)\b", text)}


def extract_events_from_async_contract(path: Path) -> list[str]:
    if not path.exists():
        return []
    events: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = re.match(r"^\s*(event|topic|name)\s*:\s*(.+?)\s*$", line, re.IGNORECASE)
        if match:
            value = match.group(2).strip().strip('"').strip("'")
            if value and not value.startswith("{"):
                events.add(value)
    return sorted(events)


def build_operation_resource_name(method: str, path: str) -> str:
    return f"{method.strip().upper()} {path.strip()}"


def matches_component_id(item: object, affected_components: set[str]) -> bool:
    if not affected_components:
        return True
    if not isinstance(item, dict):
        return False
    component_id = item.get("component_id")
    if not isinstance(component_id, str) or not component_id:
        return True
    return component_id in affected_components


def build_exact_schema_table_claims(
    schema_context: object,
    table_names: list[str],
    *,
    affected_components: list[str] | None = None,
) -> list[dict[str, str]]:
    if not isinstance(schema_context, dict):
        return []
    requested = {str(item).strip().lower() for item in table_names if str(item).strip()}
    if not requested:
        return []
    affected_component_set = {item for item in (affected_components or []) if item}
    candidates_by_table: dict[str, list[dict[str, str]]] = {}
    for table in schema_context.get("tables", []):
        if not isinstance(table, dict):
            continue
        if not matches_component_id(table, affected_component_set):
            continue
        table_name = str(table.get("table_name") or "").strip().lower()
        resource_key = str(table.get("resource_key") or "").strip()
        if not table_name or not resource_key or table_name not in requested:
            continue
        candidates_by_table.setdefault(table_name, []).append(
            {
                "kind": "schema-table",
                "name": resource_key,
                "resource_key": resource_key,
                "table_name": table_name,
            }
        )
    resolved: dict[str, dict[str, str]] = {}
    for table_name, candidates in candidates_by_table.items():
        unique_candidates = {item["resource_key"]: item for item in candidates}
        if len(unique_candidates) == 1:
            resolved[table_name] = next(iter(unique_candidates.values()))
    return [resolved[key] for key in sorted(resolved)]


def extract_mermaid_participants(design_text: str) -> list[str]:
    names: set[str] = set()
    for line in design_text.splitlines():
        participant = re.match(r"^\s*participant\s+[A-Za-z_][A-Za-z0-9_]*\s+as\s+([A-Za-z_][A-Za-z0-9_]*)\s*$", line)
        if participant:
            names.add(participant.group(1))
            continue

        participant_without_alias = re.match(r"^\s*participant\s+([A-Za-z_][A-Za-z0-9_]*)\s*$", line)
        if participant_without_alias:
            names.add(participant_without_alias.group(1))
            continue

        class_decl = re.match(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\b", line)
        if class_decl:
            names.add(class_decl.group(1))

    return sorted(names)


def build_design_resource_claims(
    *,
    paths: list[str],
    tables: list[str],
    events: list[str],
    operations: list[dict[str, str]] | None = None,
    schema_table_claims: list[dict[str, str]] | None = None,
    omit_generic_tables_for_exact: bool = False,
) -> list[dict[str, str]]:
    claims: dict[str, dict[str, str]] = {}
    covered_paths: set[str] = set()
    exact_table_names = {
        str(item.get("table_name") or "").strip().lower()
        for item in (schema_table_claims or [])
        if isinstance(item, dict)
    }

    def add_claim(kind: str, name: str) -> None:
        if not name:
            return
        resource_key = f"{kind}::{name}"
        claims[resource_key] = {
            "kind": kind,
            "name": name,
            "resource_key": resource_key,
        }

    for operation in operations or []:
        method = str(operation.get("method") or "").strip().upper()
        path = str(operation.get("path") or "").strip()
        if not method or not path:
            continue
        covered_paths.add(path)
        add_claim("operation", build_operation_resource_name(method, path))

    for path_name in paths:
        if path_name in covered_paths:
            continue
        add_claim("path", path_name)
    for table_name in tables:
        if omit_generic_tables_for_exact and table_name.strip().lower() in exact_table_names:
            continue
        add_claim("table", table_name)
    for event_name in events:
        add_claim("event", event_name)
    for claim in schema_table_claims or []:
        resource_key = str(claim.get("resource_key") or "")
        if not resource_key:
            continue
        claims[resource_key] = {key: str(value) for key, value in claim.items() if value is not None}
    return [claims[key] for key in sorted(claims)]


def build_design_resource_claims_for_pack(
    *,
    openapi_path: Path,
    data_model_path: Path,
    async_contract_path: Path | None = None,
    schema_context: object | None = None,
    affected_components: list[str] | None = None,
    omit_generic_tables_for_exact: bool = False,
) -> list[dict[str, str]]:
    paths = extract_paths_from_openapi(openapi_path)
    operations = extract_operations_from_openapi(openapi_path)
    tables = extract_tables_from_data_model(data_model_path)
    events = extract_events_from_async_contract(async_contract_path) if isinstance(async_contract_path, Path) else []
    schema_table_claims = build_exact_schema_table_claims(
        schema_context,
        tables,
        affected_components=affected_components,
    )
    return build_design_resource_claims(
        paths=paths,
        tables=tables,
        events=events,
        operations=operations,
        schema_table_claims=schema_table_claims,
        omit_generic_tables_for_exact=omit_generic_tables_for_exact,
    )


def summarize_resource_claims(resource_claims: list[dict[str, str]]) -> dict[str, object]:
    names_by_kind: dict[str, list[str]] = {}
    resource_keys_by_kind: dict[str, list[str]] = {}
    for claim in resource_claims:
        if not isinstance(claim, dict):
            continue
        kind = str(claim.get("kind") or "unknown")
        name = str(claim.get("name") or "")
        resource_key = str(claim.get("resource_key") or "")
        if name:
            names_by_kind.setdefault(kind, []).append(name)
        if resource_key:
            resource_keys_by_kind.setdefault(kind, []).append(resource_key)

    normalized_names = {kind: sorted(set(values)) for kind, values in names_by_kind.items()}
    normalized_keys = {kind: sorted(set(values)) for kind, values in resource_keys_by_kind.items()}
    counts_by_kind = {kind: len(values) for kind, values in normalized_names.items()}
    highlights = {
        kind: normalized_names[kind]
        for kind in ("operation", "schema-table", "table", "event", "path")
        if kind in normalized_names
    }
    return {
        "total": len([claim for claim in resource_claims if isinstance(claim, dict)]),
        "kinds": sorted(normalized_names),
        "counts_by_kind": counts_by_kind,
        "names_by_kind": normalized_names,
        "resource_keys_by_kind": normalized_keys,
        "highlights": highlights,
    }
