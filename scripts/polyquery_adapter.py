#!/usr/bin/env python3
"""
polyquery_adapter.py

Minimal adapter for turning PolyQuery MCP table metadata into SDD
schema-context.json compatible table entries.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "config" / "polyquery.json"


class PolyQueryError(RuntimeError):
    pass


@dataclass
class PolyQuerySource:
    db_type: str
    connection_name: str | None
    schema_name: str | None
    tables: list[str]
    include_tables: list[str]
    exclude_tables: list[str]


@dataclass
class DiscoverySettings:
    mode: str
    max_tables: int
    on_ambiguous: str


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PolyQueryError(f"文件不存在: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PolyQueryError(f"JSON 格式非法: {path}") from exc


def resolve_path(path: str | Path) -> Path:
    candidate = path if isinstance(path, Path) else Path(path)
    return candidate if candidate.is_absolute() else (ROOT / candidate).resolve()


def load_polyquery_config(config_path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    if not config_path.exists():
        raise PolyQueryError(f"缺少 polyquery 配置文件: {config_path}")
    config = read_json(config_path)
    if not isinstance(config, dict):
        raise PolyQueryError(f"polyquery 配置不是对象: {config_path}")
    return config


def parse_sources(config: dict[str, Any]) -> list[PolyQuerySource]:
    raw_sources = config.get("sources")
    if raw_sources is None:
        return []
    if not isinstance(raw_sources, list):
        raise PolyQueryError("polyquery 配置中的 sources 必须是数组")

    sources: list[PolyQuerySource] = []
    for index, raw in enumerate(raw_sources, start=1):
        if not isinstance(raw, dict):
            raise PolyQueryError(f"sources[{index}] 不是对象")
        db_type = str(raw.get("db_type") or "").strip()
        if not db_type:
            raise PolyQueryError(f"sources[{index}] 缺少 db_type")
        connection_name = raw.get("connection_name")
        schema_name = raw.get("schema_name")
        sources.append(
            PolyQuerySource(
                db_type=db_type,
                connection_name=str(connection_name) if connection_name else None,
                schema_name=str(schema_name) if schema_name else None,
                tables=[str(item) for item in raw.get("tables", []) if isinstance(item, str)],
                include_tables=[str(item) for item in raw.get("include_tables", []) if isinstance(item, str)],
                exclude_tables=[str(item) for item in raw.get("exclude_tables", []) if isinstance(item, str)],
            )
        )
    return sources


def parse_discovery_settings(config: dict[str, Any]) -> DiscoverySettings:
    raw = config.get("discovery")
    discovery = raw if isinstance(raw, dict) else {}
    return DiscoverySettings(
        mode=str(discovery.get("mode") or "agent"),
        max_tables=int(discovery.get("max_tables") or 30),
        on_ambiguous=str(discovery.get("on_ambiguous") or "require-confirmation"),
    )


def normalize_env_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    return os.path.expandvars(str(value))


class McpStdioClient:
    def __init__(self, command: list[str], env: dict[str, str] | None = None, timeout_seconds: int = 30) -> None:
        self.command = command
        self.env = env or {}
        self.timeout_seconds = timeout_seconds
        self.process: subprocess.Popen[str] | None = None
        self._request_id = 0

    def __enter__(self) -> "McpStdioClient":
        effective_env = os.environ.copy()
        effective_env.update({key: normalize_env_value(value) for key, value in self.env.items()})
        self.process = subprocess.Popen(
            self.command,
            cwd=str(ROOT),
            env=effective_env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "sdd-polyquery-adapter", "version": "0.1.0"},
            },
        )
        self.notify("notifications/initialized", {})
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self.process is None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()

    def notify(self, method: str, params: dict[str, Any]) -> None:
        if self.process is None or self.process.stdin is None:
            raise PolyQueryError("MCP 进程未启动")
        message = {"jsonrpc": "2.0", "method": method, "params": params}
        self.process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if self.process is None or self.process.stdin is None or self.process.stdout is None:
            raise PolyQueryError("MCP 进程未启动")
        self._request_id += 1
        request_id = self._request_id
        message = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        self.process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

        deadline = time.time() + self.timeout_seconds
        while time.time() < deadline:
            line = self.process.stdout.readline()
            if not line:
                if self.process.poll() is not None:
                    stderr = self.process.stderr.read() if self.process.stderr else ""
                    raise PolyQueryError(f"MCP 进程已退出: {stderr.strip()}")
                continue
            try:
                response = json.loads(line)
            except json.JSONDecodeError:
                continue
            if response.get("id") != request_id:
                continue
            if "error" in response:
                raise PolyQueryError(json.dumps(response["error"], ensure_ascii=False))
            result = response.get("result")
            if not isinstance(result, dict):
                raise PolyQueryError(f"MCP 返回结果不是对象: {response}")
            return result
        raise PolyQueryError(f"MCP 请求超时: {method}")

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        content = result.get("content")
        if result.get("isError"):
            raise PolyQueryError(extract_text_content(result))
        text = extract_text_content(result)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PolyQueryError(f"{name} 返回非 JSON 内容: {text}") from exc
        if not isinstance(payload, dict):
            raise PolyQueryError(f"{name} 返回 JSON 不是对象")
        if payload.get("success") is False:
            raise PolyQueryError(str(payload.get("error") or payload))
        return payload


def extract_text_content(result: dict[str, Any]) -> str:
    content = result.get("content")
    if not isinstance(content, list):
        return ""
    chunks: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            chunks.append(str(item.get("text") or ""))
    return "\n".join(chunks)


def build_mcp_command(config: dict[str, Any]) -> tuple[list[str], dict[str, str], int]:
    mcp_config = config.get("mcp")
    if not isinstance(mcp_config, dict):
        raise PolyQueryError("polyquery 配置缺少 mcp")
    command = mcp_config.get("command")
    if not isinstance(command, str) or not command:
        raise PolyQueryError("polyquery.mcp.command 缺失")
    args = [str(item) for item in mcp_config.get("args", []) if isinstance(item, str)]
    env = {str(key): normalize_env_value(value) for key, value in (mcp_config.get("env") or {}).items()}
    timeout_seconds = int(mcp_config.get("timeout_seconds") or 30)
    return [command, *args], env, timeout_seconds


def table_name_from_info(item: object) -> str | None:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return None
    for key in ("table_name", "name", "TABLE_NAME", "collection", "key"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def filter_tables(tables: list[str], include_patterns: list[str], exclude_patterns: list[str]) -> list[str]:
    selected = tables
    if include_patterns:
        include = [re.compile(pattern, re.IGNORECASE) for pattern in include_patterns]
        selected = [table for table in selected if any(pattern.search(table) for pattern in include)]
    if exclude_patterns:
        exclude = [re.compile(pattern, re.IGNORECASE) for pattern in exclude_patterns]
        selected = [table for table in selected if not any(pattern.search(table) for pattern in exclude)]
    return sorted(set(selected), key=str.lower)


def list_tables(client: McpStdioClient, source: PolyQuerySource) -> list[str]:
    payload = client.call_tool(
        "list_tables",
        {
            "db_type": source.db_type,
            **({"connection_name": source.connection_name} if source.connection_name else {}),
        },
    )
    data = payload.get("data")
    if not isinstance(data, list):
        raise PolyQueryError("list_tables 返回 data 不是数组")
    tables = [table for table in (table_name_from_info(item) for item in data) if table]
    return filter_tables(tables, source.include_tables, source.exclude_tables)


def describe_table(client: McpStdioClient, source: PolyQuerySource, table_name: str) -> dict[str, Any]:
    arguments: dict[str, Any] = {"db_type": source.db_type, "table_name": table_name}
    if source.connection_name:
        arguments["connection_name"] = source.connection_name
    if source.schema_name:
        arguments["schema_name"] = source.schema_name
    payload = client.call_tool("describe_table", arguments)
    columns = payload.get("data")
    if not isinstance(columns, list):
        raise PolyQueryError(f"describe_table({table_name}) 返回 data 不是数组")
    return {
        "db_type": source.db_type,
        "connection_name": source.connection_name,
        "schema_name": source.schema_name,
        "table_name": table_name,
        "columns": columns,
    }


def fetch_polyquery_descriptions(config: dict[str, Any]) -> list[dict[str, Any]]:
    command, env, timeout_seconds = build_mcp_command(config)
    sources = parse_sources(config)
    if not sources:
        raise PolyQueryError("polyquery 配置缺少 sources；如需自动发现，请使用 --auto-discover specs/<feature>")
    descriptions: list[dict[str, Any]] = []
    with McpStdioClient(command, env=env, timeout_seconds=timeout_seconds) as client:
        for source in sources:
            table_names = source.tables or list_tables(client, source)
            for table_name in table_names:
                descriptions.append(describe_table(client, source, table_name))
    return descriptions


def configured_sources(client: McpStdioClient) -> list[PolyQuerySource]:
    payload = client.call_tool("list_databases", {})
    data = payload.get("data")
    if not isinstance(data, list):
        raise PolyQueryError("list_databases 返回 data 不是数组")

    sources: list[PolyQuerySource] = []
    for item in data:
        if not isinstance(item, dict) or item.get("configured") is not True:
            continue
        db_type = item.get("type")
        raw_sources = item.get("sources")
        if not isinstance(db_type, str) or not isinstance(raw_sources, list):
            continue
        for connection_name in raw_sources:
            if isinstance(connection_name, str) and connection_name:
                sources.append(
                    PolyQuerySource(
                        db_type=db_type,
                        connection_name=connection_name,
                        schema_name=None,
                        tables=[],
                        include_tables=[],
                        exclude_tables=[],
                    )
                )
    return sources


def extract_feature_table_names(feature_dir: Path) -> set[str]:
    table_names: set[str] = set()
    if not feature_dir.exists():
        return table_names
    for path in sorted(feature_dir.glob("**/*")):
        if path.is_dir() or path.suffix.lower() not in {".md", ".sql", ".yaml", ".yml", ".json"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for table_name in re.findall(r"\b(?:t|T)_[a-zA-Z0-9_]+\b", text):
            table_names.add(table_name.lower())
    return table_names


def extract_feature_keywords(feature_dir: Path) -> set[str]:
    keywords: set[str] = set()
    raw_values = [feature_dir.name]
    for path_name in ("feature-brief.md", "design-v1.md"):
        path = feature_dir / path_name
        if path.exists():
            raw_values.append(path.read_text(encoding="utf-8", errors="ignore"))

    for value in raw_values:
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", value):
            normalized = token.lower()
            if normalized in {"feature", "brief", "design", "requirement", "description", "priority"}:
                continue
            keywords.add(normalized)

    for table_name in extract_feature_table_names(feature_dir):
        for token in table_name.removeprefix("t_").split("_"):
            if len(token) >= 3:
                keywords.add(token.lower())
    return keywords


def match_candidate_tables(
    table_names: list[str],
    *,
    exact_tables: set[str],
    keywords: set[str],
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for table_name in table_names:
        normalized = table_name.lower()
        reasons: list[str] = []
        if normalized in exact_tables:
            reasons.append("exact-table-reference")
        matched_keywords = sorted(keyword for keyword in keywords if keyword in normalized)
        if matched_keywords:
            reasons.extend([f"keyword:{keyword}" for keyword in matched_keywords[:5]])
        if reasons:
            matches.append({"table_name": table_name, "reasons": reasons})
    return matches


def discover_polyquery_tables(config: dict[str, Any], feature_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    command, env, timeout_seconds = build_mcp_command(config)
    manual_sources = parse_sources(config)
    settings = parse_discovery_settings(config)
    exact_tables = extract_feature_table_names(feature_dir)
    keywords = extract_feature_keywords(feature_dir)
    descriptions: list[dict[str, Any]] = []
    discovery_report: dict[str, Any] = {
        "feature_dir": str(feature_dir),
        "mode": settings.mode,
        "max_tables": settings.max_tables,
        "exact_tables": sorted(exact_tables),
        "keywords": sorted(keywords),
        "sources": [],
        "selected_tables": [],
        "warnings": [],
    }

    with McpStdioClient(command, env=env, timeout_seconds=timeout_seconds) as client:
        sources = manual_sources or configured_sources(client)
        if not sources:
            raise PolyQueryError("polyquery 未返回任何已配置数据源")

        selected: list[tuple[PolyQuerySource, str, list[str]]] = []
        for source in sources:
            table_names = source.tables or list_tables(client, source)
            filtered_table_names = filter_tables(table_names, source.include_tables, source.exclude_tables)
            matches = match_candidate_tables(filtered_table_names, exact_tables=exact_tables, keywords=keywords)
            discovery_report["sources"].append(
                {
                    "db_type": source.db_type,
                    "connection_name": source.connection_name,
                    "schema_name": source.schema_name,
                    "table_count": len(filtered_table_names),
                    "matches": matches,
                }
            )
            for match in matches:
                selected.append((source, str(match["table_name"]), [str(reason) for reason in match["reasons"]]))

        deduped: dict[tuple[str, str | None, str | None, str], tuple[PolyQuerySource, str, list[str]]] = {}
        for source, table_name, reasons in selected:
            key = (source.db_type, source.connection_name, source.schema_name, table_name.lower())
            deduped[key] = (source, table_name, reasons)

        if len(deduped) > settings.max_tables and settings.on_ambiguous == "require-confirmation":
            discovery_report["warnings"].append(
                f"匹配到 {len(deduped)} 张表，超过 max_tables={settings.max_tables}，需要人工确认或配置 sources"
            )
            raise PolyQueryError(discovery_report["warnings"][-1])

        for source, table_name, reasons in deduped.values():
            description = describe_table(client, source, table_name)
            description["discovery_reasons"] = reasons
            descriptions.append(description)
            discovery_report["selected_tables"].append(
                {
                    "db_type": source.db_type,
                    "connection_name": source.connection_name,
                    "schema_name": source.schema_name,
                    "table_name": table_name,
                    "reasons": reasons,
                }
            )

    return descriptions, discovery_report


def column_name(column: object) -> str | None:
    if not isinstance(column, dict):
        return None
    for key in ("name", "column_name", "COLUMN_NAME", "Field", "field"):
        value = column.get(key)
        if isinstance(value, str) and value:
            return value.lower()
    return None


def column_type(column: object) -> str | None:
    if not isinstance(column, dict):
        return None
    for key in ("type", "data_type", "DATA_TYPE", "Type"):
        value = column.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def column_nullable(column: object) -> bool | None:
    if not isinstance(column, dict):
        return None
    value = column.get("nullable")
    if isinstance(value, bool):
        return value
    value = column.get("is_nullable") or column.get("NULLABLE") or column.get("Null")
    if isinstance(value, str):
        return value.upper() in {"YES", "Y", "TRUE", "NULLABLE"}
    return None


def normalize_column_detail(column: object) -> dict[str, Any] | None:
    name = column_name(column)
    if not name:
        return None
    return {
        "name": name,
        "type": column_type(column) or "",
        "nullable": column_nullable(column),
    }


def normalize_table_name(table_name: str) -> str:
    return table_name.strip().lower()


def build_schema_resource_key(
    *,
    table_name: str,
    db_type: str | None = None,
    connection_name: str | None = None,
    schema_name: str | None = None,
    component_id: str | None = None,
) -> str:
    return "::".join(
        [
            component_id or "default",
            db_type or "local",
            connection_name or "default",
            schema_name or "default",
            table_name,
        ]
    )


def description_to_table(description: dict[str, Any]) -> dict[str, Any]:
    raw_table_name = str(description.get("table_name") or "")
    if not raw_table_name:
        raise PolyQueryError(f"describe_table 缺少 table_name: {description}")
    table_name = normalize_table_name(raw_table_name)
    column_details = [
        detail
        for detail in (normalize_column_detail(column) for column in description.get("columns", []))
        if detail is not None
    ]
    columns = sorted({str(detail["name"]) for detail in column_details})
    source_parts = [
        "polyquery",
        str(description.get("db_type") or "unknown"),
        str(description.get("connection_name") or "default"),
        str(description.get("schema_name") or "default"),
        table_name,
    ]
    db_type = str(description.get("db_type") or "unknown")
    connection_name = str(description.get("connection_name") or "default")
    schema_name = str(description.get("schema_name") or "default")
    component_id = str(description.get("component_id") or "default")
    return {
        "table_name": table_name,
        "db_type": db_type,
        "connection_name": connection_name,
        "schema_name": schema_name,
        "component_id": component_id,
        "resource_key": build_schema_resource_key(
            table_name=table_name,
            db_type=db_type,
            connection_name=connection_name,
            schema_name=schema_name,
            component_id=component_id,
        ),
        "columns": columns,
        "declared_columns": columns,
        "sql_columns": [],
        "indexed_columns": [],
        "sources": [":".join(source_parts)],
        "column_details": column_details,
    }


def descriptions_to_schema_context(
    descriptions: list[dict[str, Any]],
    *,
    source: str = "polyquery",
    discovery_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tables = [description_to_table(description) for description in descriptions]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "scenario": "ready" if tables else "new-table",
        "tables": sorted(tables, key=lambda item: str(item["table_name"])),
    }
    if discovery_report is not None:
        payload["discovery"] = discovery_report
    return payload


def load_polyquery_snapshot(snapshot_path: Path) -> dict[str, Any]:
    snapshot = read_json(snapshot_path)
    if not isinstance(snapshot, dict):
        raise PolyQueryError(f"polyquery snapshot 不是对象: {snapshot_path}")
    if snapshot.get("__error__"):
        return {
            "__error__": snapshot.get("__error__"),
            "ts": snapshot.get("ts") or datetime.now(timezone.utc).isoformat(),
            "source": "polyquery",
        }
    raw_tables = snapshot.get("tables")
    if not isinstance(raw_tables, list):
        raise PolyQueryError(f"polyquery snapshot 缺少 tables 数组: {snapshot_path}")
    descriptions = [item for item in raw_tables if isinstance(item, dict)]
    payload = descriptions_to_schema_context(descriptions, source="polyquery-snapshot")
    payload["snapshot"] = str(snapshot_path)
    return payload


def fetch_schema_context_from_polyquery(config_path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    config = load_polyquery_config(config_path)
    descriptions = fetch_polyquery_descriptions(config)
    return descriptions_to_schema_context(descriptions, source="polyquery")


def fetch_schema_context_from_polyquery_discovery(
    feature_dir: Path,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> dict[str, Any]:
    config = load_polyquery_config(config_path)
    descriptions, discovery_report = discover_polyquery_tables(config, feature_dir)
    return descriptions_to_schema_context(descriptions, source="polyquery", discovery_report=discovery_report)
