#!/usr/bin/env python3
"""
refresh_schema_context.py

从设计包中的数据模型、SQL 迁移脚本或 polyquery MCP 生成 schema-context.json。
"""

from __future__ import annotations

import json
import re
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from attached_project import DEFAULT_ATTACHMENT_PATH, build_attachment_payload, component_id_for_path, load_attachment_config
from baseline_paths import get_active_baseline_dir
from ops_log import append_project_op
from polyquery_adapter import DEFAULT_CONFIG_PATH as DEFAULT_POLYQUERY_CONFIG_PATH
from polyquery_adapter import (
    PolyQueryError,
    build_schema_resource_key,
    fetch_schema_context_from_polyquery,
    fetch_schema_context_from_polyquery_discovery,
    load_polyquery_snapshot,
)
from versioning import resolve_feature_dir

ROOT = Path(__file__).resolve().parent.parent


TABLE_FROM_MODEL_PATTERN = re.compile(r"\|\s*[^|]+\|\s*(t_[a-zA-Z0-9_]+)\s*\|")
ALTER_TABLE_PATTERN = re.compile(r"ALTER\s+TABLE\s+(t_[a-zA-Z0-9_]+)", re.IGNORECASE)
CREATE_TABLE_PATTERN = re.compile(r"CREATE\s+TABLE\s+(t_[a-zA-Z0-9_]+)", re.IGNORECASE)
ADD_COLUMN_PATTERN = re.compile(
    r"ADD\s+COLUMN\s+([a-z_][a-z0-9_]*)\s+[A-Z]+(?:\([^)]+\))?",
    re.IGNORECASE,
)
CREATE_INDEX_PATTERN = re.compile(
    r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+([a-z_][a-z0-9_]*)\s+ON\s+(t_[a-zA-Z0-9_]+)\s*\(([^)]+)\)",
    re.IGNORECASE,
)
CREATE_TABLE_BLOCK_PATTERN = re.compile(
    r"CREATE\s+TABLE\s+(t_[a-zA-Z0-9_]+)\s*\((.*?)\)\s*;",
    re.IGNORECASE | re.DOTALL,
)
CREATE_TABLE_COLUMN_PATTERN = re.compile(
    r"^\s*([a-z_][a-z0-9_]*)\s+(varchar|char|datetime|timestamp|date|int|bigint|decimal|text|bool)\b",
    re.IGNORECASE,
)
FIELD_TABLE_ROW_PATTERN = re.compile(
    r"^\|\s*([a-z_][a-z0-9_]*)\s*\|\s*([a-zA-Z]+(?:\([^)]+\))?)\s*\|",
    re.IGNORECASE,
)


def is_validation_path(path: Path) -> bool:
    return any(part.startswith("_validation-") or part.startswith("validation-") for part in path.parts)


def normalize_source_path(path: Path, workspace_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(workspace_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def parse_data_model(
    path: Path,
    workspace_root: Path = ROOT,
    *,
    component_id: str | None = None,
) -> dict[str, dict[str, object]]:
    text = path.read_text(encoding="utf-8")
    tables = sorted(set(TABLE_FROM_MODEL_PATTERN.findall(text)))
    fields = extract_field_columns(text)
    source = normalize_source_path(path, workspace_root)

    result: dict[str, dict[str, object]] = {}
    for table_name in tables:
        resource_key = build_schema_resource_key(table_name=table_name, component_id=component_id)
        result[table_name] = {
            "table_name": table_name,
            "component_id": component_id or "default",
            "db_type": "local",
            "connection_name": "default",
            "schema_name": "default",
            "resource_key": resource_key,
            "columns": fields,
            "declared_columns": fields,
            "sql_columns": [],
            "indexed_columns": [],
            "sources": [source],
        }
    return result


def extract_field_columns(text: str) -> list[str]:
    rows = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if stripped.startswith("| 字段名 |") or stripped.startswith("| ---"):
            continue

        match = FIELD_TABLE_ROW_PATTERN.match(stripped)
        if not match:
            continue

        column_name, column_type = match.groups()
        normalized_type = column_type.lower()
        if normalized_type.startswith(
            ("varchar", "char", "datetime", "timestamp", "date", "int", "bigint", "decimal", "text", "bool")
        ):
            rows.append(column_name)

    return sorted(set(rows))


def parse_sql(
    path: Path,
    workspace_root: Path = ROOT,
    *,
    component_id: str | None = None,
) -> dict[str, dict[str, object]]:
    text = path.read_text(encoding="utf-8")
    alter_tables = sorted(set(ALTER_TABLE_PATTERN.findall(text)))
    create_tables = sorted(set(CREATE_TABLE_PATTERN.findall(text)))
    tables = sorted(set(alter_tables) | set(create_tables))

    sql_columns_by_table: dict[str, list[str]] = {}
    for table_name in alter_tables:
        sql_columns_by_table.setdefault(table_name, [])
        sql_columns_by_table[table_name].extend(ADD_COLUMN_PATTERN.findall(text))
    for table_name, block in CREATE_TABLE_BLOCK_PATTERN.findall(text):
        sql_columns_by_table.setdefault(table_name, [])
        for raw_line in block.splitlines():
            match = CREATE_TABLE_COLUMN_PATTERN.match(raw_line.strip().rstrip(","))
            if match:
                sql_columns_by_table[table_name].append(match.group(1))
    indexed_columns_by_table: dict[str, list[str]] = {}
    for _, table_name, column_block in CREATE_INDEX_PATTERN.findall(text):
        indexed_columns_by_table.setdefault(table_name, [])
        indexed_columns_by_table[table_name].extend(
            [column.strip() for column in column_block.split(",") if column.strip()]
        )

    source = normalize_source_path(path, workspace_root)
    result: dict[str, dict[str, object]] = {}
    for table_name in tables:
        table_columns = sorted(set(sql_columns_by_table.get(table_name, [])))
        resource_key = build_schema_resource_key(table_name=table_name, component_id=component_id)
        result[table_name] = {
            "table_name": table_name,
            "component_id": component_id or "default",
            "db_type": "local",
            "connection_name": "default",
            "schema_name": "default",
            "resource_key": resource_key,
            "columns": table_columns,
            "declared_columns": [],
            "sql_columns": table_columns,
            "indexed_columns": sorted(set(indexed_columns_by_table.get(table_name, []))),
            "sources": [source],
        }
    return result


def merge_tables(items: list[dict[str, dict[str, object]]]) -> list[dict[str, object]]:
    merged: dict[str, dict[str, object]] = {}

    for item in items:
        for table_name, data in item.items():
            merge_key = str(data.get("resource_key") or table_name)
            if merge_key not in merged:
                merged[merge_key] = {
                    "table_name": table_name,
                    "component_id": data.get("component_id", "default"),
                    "db_type": data.get("db_type", "local"),
                    "connection_name": data.get("connection_name", "default"),
                    "schema_name": data.get("schema_name", "default"),
                    "resource_key": data.get("resource_key"),
                    "columns": list(data.get("columns", [])),
                    "declared_columns": list(data.get("declared_columns", [])),
                    "sql_columns": list(data.get("sql_columns", [])),
                    "indexed_columns": list(data.get("indexed_columns", [])),
                    "sources": list(data.get("sources", [])),
                    "column_details": list(data.get("column_details", [])),
                }
                continue

            existing = merged[merge_key]
            existing["columns"] = sorted(set(existing.get("columns", [])) | set(data.get("columns", [])))
            existing["declared_columns"] = sorted(
                set(existing.get("declared_columns", [])) | set(data.get("declared_columns", []))
            )
            existing["sql_columns"] = sorted(set(existing.get("sql_columns", [])) | set(data.get("sql_columns", [])))
            existing["indexed_columns"] = sorted(
                set(existing.get("indexed_columns", [])) | set(data.get("indexed_columns", []))
            )
            existing["sources"] = sorted(set(existing.get("sources", [])) | set(data.get("sources", [])))
            existing["column_details"] = list(existing.get("column_details", [])) + [
                detail
                for detail in data.get("column_details", [])
                if isinstance(detail, dict)
                and detail not in existing.get("column_details", [])
            ]

    return sorted(merged.values(), key=lambda item: str(item["table_name"]).lower())


def source_signature(payload: dict[str, object]) -> str:
    tables = payload.get("tables", [])
    table_items = tables if isinstance(tables, list) else []
    relevant = {
        "source": payload.get("source"),
        "fallback_from": payload.get("fallback_from"),
        "design_roots": payload.get("design_roots", []),
        "schema_roots": payload.get("schema_roots", []),
        "tables": [
            {
                "table_name": item.get("table_name"),
                "sources": item.get("sources", []),
            }
            for item in table_items
            if isinstance(item, dict)
        ],
    }
    content = json.dumps(relevant, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def attach_evidence_metadata(payload: dict[str, object], *, source: object | None = None) -> dict[str, object]:
    effective_source = source if source is not None else payload.get("source")
    payload["source"] = effective_source
    payload.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
    if effective_source in {"polyquery", "polyquery-snapshot"}:
        payload["evidence_level"] = "L1"
        payload["confidence"] = "high" if effective_source == "polyquery" else "medium"
    elif effective_source == "local-fallback":
        payload["evidence_level"] = "L2"
        payload["confidence"] = "low"
    else:
        payload["evidence_level"] = "L2"
        payload["confidence"] = "medium"
    payload.setdefault("ttl", "P1D")
    payload["source_signature"] = source_signature(payload)
    return payload


def write_schema_audit(
    *,
    schema_context_path: Path,
    payload: dict[str, object],
    started_at: float,
    result: str,
    error: str | None = None,
    auto_discover: str | None = None,
) -> None:
    append_project_op(
        "schema-context-refresh",
        {
            "result": result,
            "file": str(schema_context_path),
            "source": payload.get("source"),
            "fallback_from": payload.get("fallback_from"),
            "table_count": len(payload.get("tables", [])) if isinstance(payload.get("tables"), list) else 0,
            "duration_ms": int((time.perf_counter() - started_at) * 1000),
            "auto_discover": auto_discover,
            "error": error,
        },
    )


def resolve_schema_context_sources(
    *,
    attachment_path: Path = DEFAULT_ATTACHMENT_PATH,
    profile: str | None = None,
    design_roots: list[Path | str] | None,
    schema_roots: list[Path | str] | None,
    project_root: Path | str | None,
) -> dict[str, object]:
    if project_root is not None:
        payload = build_attachment_payload(
            project_root=Path(project_root),
            design_roots=[Path(item) for item in design_roots] if design_roots else None,
            schema_roots=[Path(item) for item in schema_roots] if schema_roots else None,
        )
        payload["source"] = "project_root"
        return payload

    if design_roots or schema_roots:
        return {
            "name": "cli-schema-settings",
            "project_root": None,
            "design_roots": [str(Path(item).resolve()) for item in (design_roots or [ROOT / "specs"])],
            "schema_roots": [str(Path(item).resolve()) for item in (schema_roots or [])],
            "source": "cli",
        }

    attachment = load_attachment_config(attachment_path, profile=profile)
    if attachment is not None:
        return {
            **attachment,
            "schema_roots": attachment.get("schema_roots", []),
            "source": "attachment",
        }

    return {
        "name": "current-workspace",
        "project_root": str(ROOT.resolve()),
        "design_roots": [str((ROOT / "specs").resolve())],
        "schema_roots": [
            str((ROOT / "src" / "main" / "resources").resolve()),
            str((ROOT / "sql").resolve()),
            str((ROOT / "db").resolve()),
        ],
        "source": "default",
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=None, help="显式目标项目根目录")
    parser.add_argument("--design-root", action="append", default=None, help="显式设计根目录，可重复传入")
    parser.add_argument("--schema-root", action="append", default=None, help="显式 schema 根目录，可重复传入")
    parser.add_argument(
        "--attachment-file",
        default=str(DEFAULT_ATTACHMENT_PATH),
        help="附着目标项目配置文件路径，默认 .spec/attached-project.json",
    )
    parser.add_argument("--profile", default=None, help="optional attachment profile name")
    parser.add_argument(
        "--output",
        default=None,
        help="输出 schema-context.json 路径，默认写入 .spec/baseline/schema-context.json",
    )
    parser.add_argument("--from-polyquery", action="store_true", help="优先从 polyquery MCP 生成 schema-context.json")
    parser.add_argument(
        "--polyquery-config",
        default=str(DEFAULT_POLYQUERY_CONFIG_PATH),
        help="polyquery 接入配置，默认 config/polyquery.json",
    )
    parser.add_argument(
        "--polyquery-snapshot",
        default=None,
        help="从已保存的 polyquery snapshot 生成 schema-context.json，用于 CI 或离线复核",
    )
    parser.add_argument(
        "--auto-discover",
        default=None,
        help="指定 specs/<feature> 目录，由 agent/SDD 根据设计材料自动发现需要沉淀的表",
    )
    parser.add_argument(
        "--polyquery-fallback",
        choices=["local", "fail"],
        default="local",
        help="polyquery 调用失败时是否回退本地 SQL / design-pack 快照",
    )
    args = parser.parse_args()
    started_at = time.perf_counter()

    attachment_path = Path(args.attachment_file)
    baseline_dir = get_active_baseline_dir(
        attachment_path=attachment_path,
        profile=args.profile,
        create=True,
        migrate_legacy=True,
    )
    baseline_dir.mkdir(parents=True, exist_ok=True)
    schema_context_path = Path(args.output) if args.output else (baseline_dir / "schema-context.json")
    schema_context_path = schema_context_path if schema_context_path.is_absolute() else (ROOT / schema_context_path).resolve()
    schema_context_path.parent.mkdir(parents=True, exist_ok=True)

    if args.from_polyquery:
        try:
            if args.polyquery_snapshot:
                payload = load_polyquery_snapshot(Path(args.polyquery_snapshot))
            elif args.auto_discover:
                payload = fetch_schema_context_from_polyquery_discovery(
                    resolve_feature_dir(args.auto_discover, attachment_path=attachment_path, profile=args.profile),
                    Path(args.polyquery_config),
                )
            else:
                payload = fetch_schema_context_from_polyquery(Path(args.polyquery_config))

            if payload.get("__error__"):
                attach_evidence_metadata(payload, source=payload.get("source") or "polyquery")
                schema_context_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                write_schema_audit(
                    schema_context_path=schema_context_path,
                    payload=payload,
                    started_at=started_at,
                    result="fail",
                    error=str(payload.get("__error__")),
                    auto_discover=args.auto_discover,
                )
                print("[FAIL] polyquery snapshot 包含错误标记")
                print(f"  - file:  {schema_context_path}")
                print(f"  - error: {payload.get('__error__')}")
                return 1

            attach_evidence_metadata(payload)
            schema_context_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            write_schema_audit(
                schema_context_path=schema_context_path,
                payload=payload,
                started_at=started_at,
                result="ok",
                auto_discover=args.auto_discover,
            )
            print("[OK] schema-context 已由 polyquery 生成")
            print(f"  - file:  {schema_context_path}")
            print(f"  - count: {len(payload.get('tables', []))}")
            print(f"  - source:{payload.get('source')}")
            print(f"  - scenario:{payload.get('scenario')}")
            return 0
        except PolyQueryError as exc:
            if args.polyquery_fallback == "fail":
                error_payload = {
                    "__error__": str(exc),
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "source": "polyquery",
                }
                attach_evidence_metadata(error_payload, source="polyquery")
                schema_context_path.write_text(json.dumps(error_payload, ensure_ascii=False, indent=2), encoding="utf-8")
                write_schema_audit(
                    schema_context_path=schema_context_path,
                    payload=error_payload,
                    started_at=started_at,
                    result="fail",
                    error=str(exc),
                    auto_discover=args.auto_discover,
                )
                print("[FAIL] polyquery schema-context 生成失败")
                print(f"  - file:  {schema_context_path}")
                print(f"  - error: {exc}")
                return 1
            print("[WARN] polyquery schema-context 生成失败，回退本地快照")
            print(f"  - error: {exc}")

    source_settings = resolve_schema_context_sources(
        attachment_path=attachment_path,
        profile=args.profile,
        design_roots=[Path(item) for item in args.design_root] if args.design_root else None,
        schema_roots=[Path(item) for item in args.schema_root] if args.schema_root else None,
        project_root=Path(args.project_root) if args.project_root else None,
    )
    design_roots_resolved = [Path(item) for item in source_settings.get("design_roots", []) if isinstance(item, str)]
    schema_roots_resolved = [Path(item) for item in source_settings.get("schema_roots", []) if isinstance(item, str)]

    table_items: list[dict[str, dict[str, object]]] = []
    for design_root in design_roots_resolved:
        if not design_root.exists():
            continue
        for path in sorted(design_root.glob("**/design-pack/数据模型.md")):
            if is_validation_path(path.relative_to(design_root)):
                continue
            component_id = component_id_for_path(
                path,
                source_settings,
                preferred_fields=("design_roots", "scan_roots", "schema_roots"),
            )
            table_items.append(parse_data_model(path, workspace_root=ROOT, component_id=component_id))
    for schema_root in schema_roots_resolved:
        if not schema_root.exists():
            continue
        for path in sorted(schema_root.glob("**/*.sql")):
            if is_validation_path(path.relative_to(schema_root)):
                continue
            component_id = component_id_for_path(
                path,
                source_settings,
                preferred_fields=("schema_roots", "scan_roots", "design_roots"),
            )
            table_items.append(parse_sql(path, workspace_root=ROOT, component_id=component_id))

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "local-fallback" if args.from_polyquery else source_settings.get("source"),
        "fallback_from": "polyquery" if args.from_polyquery else None,
        "design_roots": [str(path.resolve()) for path in design_roots_resolved],
        "schema_roots": [str(path.resolve()) for path in schema_roots_resolved],
        "tables": merge_tables(table_items),
    }
    attach_evidence_metadata(payload)
    schema_context_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_schema_audit(
        schema_context_path=schema_context_path,
        payload=payload,
        started_at=started_at,
        result="ok",
        auto_discover=args.auto_discover,
    )

    print("[OK] schema-context 快照已生成")
    print(f"  - file:  {schema_context_path}")
    print(f"  - count: {len(payload['tables'])}")
    print(f"  - source:{payload['source']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
