#!/usr/bin/env python3
"""
check_design_truthfulness.py

Gate 2：真实性 / 结构约束校验。
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from baseline_extractors import (
    extract_created_tables,
    extract_operations_from_openapi,
    extract_paths_from_openapi,
    extract_table_field_specs_from_data_model,
    extract_table_fields_from_data_model,
    extract_tables_from_data_model,
)
from attached_project import DEFAULT_ATTACHMENT_PATH, resolve_module_map_scan_settings, source_signature
from baseline_paths import get_active_baseline_dir
from bootstrap_utils import BOOTSTRAP_REPORT_NAME, BOOTSTRAP_REQUIRED_FILES
from design_evidence import hash_file, hash_tree, resolve_design_pack_dir
from feature_brief import extract_affected_components
from gate_report import write_gate_section
from refresh_schema_context import resolve_schema_context_sources, source_signature as schema_context_source_signature
from versioning import detect_latest_design_path, reports_dir_for_design, resolve_feature_dir


GREENFIELD_BOOTSTRAP_KEYWORDS = {
    "constitution.md": ["硬阻断", "测试", "回滚"],
    "architecture.md": ["接口层", "应用层", "领域层", "基础设施层"],
    "module-layout.md": ["允许的依赖方向", "禁止的依赖方向"],
    "bootstrap-plan.md": ["日志", "测试框架", "监控与告警"],
}


def extract_yaml_blocks(text: str) -> list[str]:
    matches = re.findall(r"```yaml\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return matches if matches else [text]


def extract_scalar(yaml_text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", yaml_text)
    if not match:
        return None
    return match.group(1).strip().strip('"').strip("'")


def extract_project_mode(brief_content: str) -> str:
    yaml_text = "\n".join(extract_yaml_blocks(brief_content))
    return extract_scalar(yaml_text, "project_mode") or "brownfield"


def extract_risk_tier(brief_content: str) -> str:
    yaml_text = "\n".join(extract_yaml_blocks(brief_content))
    return (extract_scalar(yaml_text, "risk_tier") or "low").lower()


def extract_feature_name(brief_content: str, feature_dir: Path) -> str:
    yaml_text = "\n".join(extract_yaml_blocks(brief_content))
    return extract_scalar(yaml_text, "feature_name") or feature_dir.name


def extract_req_ids(brief_content: str) -> list[str]:
    req_ids = re.findall(r"req_id:\s*(REQ-\d+)", brief_content)
    if not req_ids:
        req_ids = re.findall(r"-\s*(REQ-\d+)", brief_content)
    return sorted(set(req_ids))


def check_bootstrap_artifacts(feature_dir: Path) -> tuple[list[str], list[str]]:
    checks: list[str] = []
    errors: list[str] = []

    required_files = [*BOOTSTRAP_REQUIRED_FILES, BOOTSTRAP_REPORT_NAME]
    missing = [name for name in required_files if not (feature_dir / name).exists()]
    if missing:
        errors.append(f"greenfield bootstrap 产物缺失: {', '.join(missing)}")
        return checks, errors

    report_path = feature_dir / BOOTSTRAP_REPORT_NAME
    try:
        scaffold_report = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        errors.append(f"bootstrap scaffold-report.json 不是合法 JSON: {report_path}")
        return checks, errors

    if scaffold_report.get("result") != "PASS":
        errors.append(f"bootstrap scaffold-report.json 结果不是 PASS: {report_path}")
    else:
        checks.append("greenfield bootstrap scaffold-report 为 PASS")

    for file_name, keywords in GREENFIELD_BOOTSTRAP_KEYWORDS.items():
        target = feature_dir / file_name
        text = target.read_text(encoding="utf-8", errors="ignore")
        missing_keywords = [keyword for keyword in keywords if keyword not in text]
        if missing_keywords:
            errors.append(f"bootstrap {file_name} 缺少关键语义: {', '.join(missing_keywords)}")
        else:
            checks.append(f"bootstrap {file_name} 具备最小结构语义")

    return checks, errors


def collect_design_pack_coverage(design_pack_dir: Path, req_ids: list[str]) -> dict[str, object]:
    if design_pack_dir.name != "design-pack" and (design_pack_dir / "design-pack").exists():
        design_pack_dir = design_pack_dir / "design-pack"
    if not design_pack_dir.exists():
        return {
            "coverage": {req: [] for req in req_ids},
            "file_issues": [],
            "errors": ["Missing design-pack directory"],
        }

    coverage = {req: [] for req in req_ids}
    file_issues: list[str] = []
    design_files = [
        *design_pack_dir.glob("*.md"),
        *design_pack_dir.glob("*.yaml"),
        *design_pack_dir.glob("*.yml"),
        *design_pack_dir.glob("*.sql"),
    ]

    for design_file in design_files:
        content = design_file.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        if len([line for line in lines if line.strip()]) < 10 and design_file.suffix == ".md":
            file_issues.append(f"File {design_file.name} is too thin (less than 10 meaningful lines).")
        for req in req_ids:
            if design_pack_has_req_evidence(design_file, lines, req):
                coverage[req].append(design_file.name)

    missing_reqs = [req for req, files in coverage.items() if not files]
    errors = [f"REQ-ID 未被 design-pack 覆盖: {', '.join(missing_reqs)}"] if missing_reqs else []
    errors.extend(file_issues)

    return {
        "coverage": coverage,
        "file_issues": file_issues,
        "errors": errors,
    }


def design_pack_has_req_evidence(design_file: Path, lines: list[str], req_id: str) -> bool:
    lower_name = design_file.name.lower()
    if lower_name.endswith(".openapi.yaml") or lower_name.endswith(".openapi.yml"):
        return False
    if design_file.suffix.lower() == ".sql":
        return False

    for line in lines:
        stripped = line.strip()
        if req_id not in stripped:
            continue
        if not stripped or stripped.startswith(("#", "//")):
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            return True
        if re.search(r"(?i)\b(req_ids?|acceptance|验收|对应\s*REQ-ID|需求|契约)\b", stripped):
            return True
        if re.match(r"^-\s*(req_ids?\s*:)?\s*" + re.escape(req_id) + r"\b", stripped, re.IGNORECASE):
            return True
    return False


def read_json_file(path: Path, default: object) -> object:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def is_strict_enabled(explicit: bool = False) -> bool:
    return explicit or os.environ.get("SDD_STRICT", "").lower() in {"1", "true", "yes", "on"}


def baseline_file_evidence(path: Path, *, default_level: str, default_confidence: str) -> dict[str, object]:
    payload = read_json_file(path, {})
    evidence_level = default_level
    confidence = default_confidence
    source = None
    if isinstance(payload, dict):
        evidence_level = str(payload.get("evidence_level") or evidence_level)
        confidence = str(payload.get("confidence") or confidence)
        source = payload.get("source")
    return {
        "source": str(path),
        "hash": hash_file(path),
        "evidence_level": evidence_level,
        "confidence": confidence,
        "source_type": source,
    }


def validate_schema_context_source(
    schema_context_path: Path,
    *,
    risk_tier: str,
    strict: bool,
) -> tuple[list[str], list[str], dict[str, object]]:
    warnings: list[str] = []
    errors: list[str] = []
    schema_context = read_json_file(schema_context_path, {})
    if not isinstance(schema_context, dict):
        return warnings, errors, {"source": None, "fallback_from": None}

    source = schema_context.get("source")
    fallback_from = schema_context.get("fallback_from")
    metadata = {
        "source": source,
        "fallback_from": fallback_from,
        "confidence": schema_context.get("confidence"),
        "evidence_level": schema_context.get("evidence_level"),
    }
    if source == "local-fallback":
        message = "schema-context 使用 local-fallback，事实源不是实时数据库元数据"
        if strict or risk_tier == "high":
            errors.append(message)
        else:
            warnings.append(message)
    return warnings, errors, metadata


def validate_module_map_quality(
    module_map_path: Path,
    *,
    strict: bool,
) -> tuple[list[str], list[str], dict[str, object]]:
    warnings: list[str] = []
    errors: list[str] = []
    module_map = read_json_file(module_map_path, {})
    if not isinstance(module_map, dict):
        return warnings, errors, {"scanner": None, "unsupported_features": []}

    confidence = str(module_map.get("confidence") or "").lower()
    unsupported_features = module_map.get("unsupported_features")
    if not isinstance(unsupported_features, list):
        unsupported_features = []
    metadata = {
        "scanner": module_map.get("scanner"),
        "unsupported_features": unsupported_features,
        "scan_quality": module_map.get("scan_quality") if isinstance(module_map.get("scan_quality"), dict) else {},
    }
    if confidence == "low":
        suffix = ""
        if unsupported_features:
            suffix = "，unsupported_features=" + ", ".join(str(item) for item in unsupported_features)
        message = f"module-map 可信度较低，不能单独支撑高置信实现追溯{suffix}"
        if strict:
            errors.append(message)
        else:
            warnings.append(message)
    return warnings, errors, metadata


def validate_attached_project_signature(
    module_map_path: Path,
    *,
    attachment_path: Path = DEFAULT_ATTACHMENT_PATH,
    strict: bool,
) -> tuple[list[str], list[str], dict[str, object]]:
    warnings: list[str] = []
    errors: list[str] = []
    metadata: dict[str, object] = {"attachment_signature_status": "unknown"}
    if not attachment_path.exists():
        metadata["attachment_signature_status"] = "no-attachment"
        return warnings, errors, metadata

    module_map = read_json_file(module_map_path, {})
    if not isinstance(module_map, dict):
        return warnings, errors, metadata
    recorded_signature = module_map.get("source_signature")
    if not isinstance(recorded_signature, str) or not recorded_signature:
        metadata["attachment_signature_status"] = "missing"
        return warnings, errors, metadata

    current_settings = resolve_module_map_scan_settings(
        attachment_path=attachment_path,
        scan_roots=None,
        design_roots=None,
        project_root=None,
    )
    if current_settings.get("source") != "attachment":
        metadata["attachment_signature_status"] = "no-attachment"
        return warnings, errors, metadata

    current_signature = source_signature(current_settings)
    metadata["attachment_signature_status"] = "matched" if current_signature == recorded_signature else "changed"
    metadata["current_source_signature"] = current_signature
    metadata["recorded_source_signature"] = recorded_signature
    if current_signature != recorded_signature:
        message = "attached project 配置已变化，module-map baseline 需要刷新"
        if strict:
            errors.append(message)
        else:
            warnings.append(message)
    return warnings, errors, metadata


def validate_schema_context_signature(
    schema_context_path: Path,
    *,
    attachment_path: Path = DEFAULT_ATTACHMENT_PATH,
    strict: bool,
) -> tuple[list[str], list[str], dict[str, object]]:
    warnings: list[str] = []
    errors: list[str] = []
    metadata: dict[str, object] = {"schema_context_signature_status": "unknown"}
    if not attachment_path.exists():
        metadata["schema_context_signature_status"] = "no-attachment"
        return warnings, errors, metadata

    schema_context = read_json_file(schema_context_path, {})
    if not isinstance(schema_context, dict):
        return warnings, errors, metadata
    recorded_signature = schema_context.get("source_signature")
    if not isinstance(recorded_signature, str) or not recorded_signature:
        metadata["schema_context_signature_status"] = "missing"
        return warnings, errors, metadata

    source = str(schema_context.get("source") or "")
    if source not in {"attachment", "local-fallback", "project_root", "default", "cli"}:
        metadata["schema_context_signature_status"] = "not-applicable"
        return warnings, errors, metadata

    current_settings = resolve_schema_context_sources(
        attachment_path=attachment_path,
        design_roots=None,
        schema_roots=None,
        project_root=None,
    )
    if current_settings.get("source") != "attachment":
        metadata["schema_context_signature_status"] = "no-attachment"
        return warnings, errors, metadata

    expected_payload = dict(schema_context)
    expected_payload["design_roots"] = current_settings.get("design_roots", [])
    expected_payload["schema_roots"] = current_settings.get("schema_roots", [])
    if source != "local-fallback":
        expected_payload["source"] = current_settings.get("source")
    current_signature = schema_context_source_signature(expected_payload)
    metadata["schema_context_signature_status"] = "matched" if current_signature == recorded_signature else "changed"
    metadata["current_schema_source_signature"] = current_signature
    metadata["recorded_schema_source_signature"] = recorded_signature
    if current_signature != recorded_signature:
        message = "schema-context 配置已变化，schema-context baseline 需要刷新"
        if strict:
            errors.append(message)
        else:
            warnings.append(message)
    return warnings, errors, metadata


def normalize_endpoint_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    normalized = value.strip()
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    return re.sub(r"/+", "/", normalized.rstrip("/") or "/")


def normalize_http_method(value: object) -> str:
    return str(value or "").strip().upper()


def extract_controller_endpoints_from_module_map(module_map: object) -> list[dict[str, str]]:
    if not isinstance(module_map, dict):
        return []
    endpoints: list[dict[str, str]] = []
    for item in module_map.get("classes", []):
        if not isinstance(item, dict):
            continue
        class_name = str(item.get("simple_name") or item.get("class_name") or "")
        for endpoint in item.get("endpoints", []):
            if not isinstance(endpoint, dict):
                continue
            path = normalize_endpoint_path(endpoint.get("path"))
            method = normalize_http_method(endpoint.get("method"))
            if not path or not method:
                continue
            endpoints.append(
                {
                    "path": path,
                    "method": method,
                    "operation_id": str(endpoint.get("operation_id") or endpoint.get("method_name") or ""),
                    "method_name": str(endpoint.get("method_name") or ""),
                    "class_name": class_name,
                }
            )
    return endpoints


def validate_openapi_controller_mapping(
    openapi_operations: list[dict[str, str]],
    module_map: object,
) -> tuple[list[str], list[str]]:
    checks: list[str] = []
    errors: list[str] = []
    if not openapi_operations:
        return checks, errors
    controller_endpoints = extract_controller_endpoints_from_module_map(module_map)
    if not controller_endpoints:
        return checks, errors

    endpoints_by_resource: dict[tuple[str, str], list[dict[str, str]]] = {}
    for endpoint in controller_endpoints:
        endpoints_by_resource.setdefault((endpoint["path"], endpoint["method"]), []).append(endpoint)

    missing: list[str] = []
    operation_mismatches: list[str] = []
    for operation in openapi_operations:
        path = normalize_endpoint_path(operation.get("path"))
        method = normalize_http_method(operation.get("method"))
        operation_id = str(operation.get("operation_id") or "")
        matches = endpoints_by_resource.get((path, method), [])
        if not matches:
            missing.append(f"{method} {path}")
            continue
        if operation_id:
            candidate_ids = {str(item.get("operation_id") or item.get("method_name") or "") for item in matches}
            if operation_id not in candidate_ids:
                operation_mismatches.append(f"{method} {path}: openapi={operation_id}, controller={', '.join(sorted(candidate_ids))}")

    if missing:
        errors.append("OpenAPI 接口未映射到真实 Controller: " + ", ".join(sorted(set(missing))))
    if operation_mismatches:
        errors.append("OpenAPI operationId 与 Controller 方法不一致: " + ", ".join(sorted(set(operation_mismatches))))
    if not missing and not operation_mismatches:
        checks.append("OpenAPI path/method/operationId 均映射到真实 Controller")
    return checks, errors


def parse_ttl(value: object) -> timedelta | None:
    if isinstance(value, (int, float)):
        return timedelta(seconds=float(value))
    if not isinstance(value, str) or not value:
        return None
    if value.isdigit():
        return timedelta(seconds=int(value))
    match = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", value)
    if not match:
        return None
    days = int(match.group(1) or 0)
    hours = int(match.group(2) or 0)
    minutes = int(match.group(3) or 0)
    seconds = int(match.group(4) or 0)
    return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)


def parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def validate_baseline_freshness(
    label: str,
    path: Path,
    *,
    strict: bool,
) -> tuple[list[str], list[str], dict[str, object]]:
    warnings: list[str] = []
    errors: list[str] = []
    payload = read_json_file(path, {})
    metadata: dict[str, object] = {"freshness": "unknown"}
    if not isinstance(payload, dict):
        return warnings, errors, metadata

    generated_at = parse_datetime(payload.get("generated_at"))
    ttl = parse_ttl(payload.get("ttl"))
    metadata["generated_at"] = payload.get("generated_at")
    metadata["ttl"] = payload.get("ttl")
    if generated_at is None or ttl is None:
        return warnings, errors, metadata

    expires_at = generated_at + ttl
    now = datetime.now(timezone.utc)
    metadata["expires_at"] = expires_at.isoformat()
    metadata["freshness"] = "stale" if now > expires_at else "fresh"
    if now > expires_at:
        message = f"{label} baseline 已过期: generated_at={generated_at.isoformat()}, ttl={payload.get('ttl')}"
        if strict:
            errors.append(message)
        else:
            warnings.append(message)
    return warnings, errors, metadata


def normalize_resource_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path(__file__).resolve().parent.parent)).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def extract_design_participants(design_text: str) -> list[str]:
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


def has_new_domain_mermaid_fallback(design_text: str) -> bool:
    return bool(
        "sequenceDiagram" in design_text
        and re.search(r"Note over \w+: .*(新领域模式|缺少可用存量类)", design_text)
    )


def normalize_schema_type(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"\([^)]*\)", "", normalized).strip()
    aliases = {
        "character varying": "varchar",
        "varchar2": "varchar",
        "nvarchar": "varchar",
        "nvarchar2": "varchar",
        "string": "varchar",
        "text": "varchar",
        "int4": "int",
        "integer": "int",
        "int8": "bigint",
        "long": "bigint",
        "bool": "boolean",
        "numeric": "decimal",
        "number": "decimal",
    }
    return aliases.get(normalized, normalized)


def parse_schema_nullable(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in {"true", "yes", "y", "1", "nullable", "可空", "是"}:
        return True
    if normalized in {"false", "no", "n", "0", "not null", "not_null", "非空", "否"}:
        return False
    return None


def is_current_feature_source(source: object, feature_dir: Path) -> bool:
    if not isinstance(source, str):
        return False
    normalized = source.replace("\\", "/")
    feature_path = normalize_resource_path(feature_dir)
    return normalized.startswith(feature_path) or f"/{feature_dir.name}/" in normalized


def matches_affected_components(item: dict[str, object], affected_components: set[str]) -> bool:
    if not affected_components:
        return True
    component_id = item.get("component_id")
    if not isinstance(component_id, str) or not component_id:
        return True
    return component_id in affected_components


def extract_jpa_entities_from_module_map(
    module_map: object,
    affected_components: set[str],
) -> dict[str, dict[str, object]]:
    if not isinstance(module_map, dict):
        return {}
    entities_by_table: dict[str, dict[str, object]] = {}
    for item in module_map.get("classes", []):
        if not isinstance(item, dict):
            continue
        if not matches_affected_components(item, affected_components):
            continue
        jpa_entity = item.get("jpa_entity")
        if not isinstance(jpa_entity, dict):
            continue
        table_name = jpa_entity.get("table_name")
        if not isinstance(table_name, str) or not table_name:
            continue
        existing = entities_by_table.setdefault(
            table_name,
            {
                "table_name": table_name,
                "columns": set(),
                "fields": set(),
                "entity_classes": set(),
            },
        )
        existing["entity_classes"].add(str(item.get("simple_name") or item.get("class_name") or table_name))
        for column in jpa_entity.get("column_mappings", []):
            if not isinstance(column, dict):
                continue
            field_name = column.get("field_name")
            column_name = column.get("column_name")
            if isinstance(field_name, str) and field_name:
                existing["fields"].add(field_name.lower())
            if isinstance(column_name, str) and column_name:
                existing["columns"].add(column_name.lower())
    return entities_by_table


def extract_mybatis_table_mappings_from_module_map(
    module_map: object,
    affected_components: set[str],
) -> dict[str, dict[str, object]]:
    if not isinstance(module_map, dict):
        return {}

    classes = [item for item in module_map.get("classes", []) if isinstance(item, dict) and matches_affected_components(item, affected_components)]
    classes_by_fqn: dict[str, dict[str, object]] = {}
    classes_by_simple_name: dict[str, list[dict[str, object]]] = {}
    for item in classes:
        fqn = item.get("fqn")
        if isinstance(fqn, str) and fqn:
            classes_by_fqn[fqn] = item
        simple_name = str(item.get("simple_name") or item.get("class_name") or "").split(".")[-1]
        if simple_name:
            classes_by_simple_name.setdefault(simple_name, []).append(item)

    def resolve_class(type_name: object) -> dict[str, object] | None:
        if not isinstance(type_name, str) or not type_name:
            return None
        if type_name in classes_by_fqn:
            return classes_by_fqn[type_name]
        simple_name = type_name.split(".")[-1]
        candidates = classes_by_simple_name.get(simple_name, [])
        return candidates[0] if len(candidates) == 1 else None

    def collect_class_mapped_fields(target_class: dict[str, object] | None) -> tuple[set[str], set[str], dict[str, str], dict[str, str]]:
        mapped_columns: set[str] = set()
        mapped_properties: set[str] = set()
        column_types: dict[str, str] = {}
        property_types: dict[str, str] = {}
        if not isinstance(target_class, dict):
            return mapped_columns, mapped_properties, column_types, property_types
        for field in target_class.get("field_details", []):
            if isinstance(field, dict):
                field_name = field.get("name")
                field_type = field.get("type")
                if isinstance(field_name, str) and field_name:
                    mapped_properties.add(field_name.lower())
                    if isinstance(field_type, str) and field_type:
                        property_types[field_name.lower()] = normalize_schema_type(field_type) or field_type.lower()
        for field in target_class.get("fields", []):
            if isinstance(field, str) and field:
                mapped_properties.add(field.lower())
        jpa_entity = target_class.get("jpa_entity")
        if isinstance(jpa_entity, dict):
            for column in jpa_entity.get("column_mappings", []):
                if not isinstance(column, dict):
                    continue
                field_name = column.get("field_name")
                column_name = column.get("column_name")
                if isinstance(field_name, str) and field_name:
                    mapped_properties.add(field_name.lower())
                    field_type = column.get("field_type")
                    if isinstance(field_type, str) and field_type:
                        property_types[field_name.lower()] = normalize_schema_type(field_type) or field_type.lower()
                if isinstance(column_name, str) and column_name:
                    mapped_columns.add(column_name.lower())
                    field_type = column.get("field_type")
                    if isinstance(field_type, str) and field_type:
                        column_types[column_name.lower()] = normalize_schema_type(field_type) or field_type.lower()
        return mapped_columns, mapped_properties, column_types, property_types

    mappings_by_table: dict[str, dict[str, object]] = {}
    for item in classes:
        mybatis_mapper = item.get("mybatis_mapper")
        if not isinstance(mybatis_mapper, dict):
            continue
        mapper_name = str(item.get("simple_name") or item.get("class_name") or mybatis_mapper.get("namespace") or "mapper")
        result_maps_by_id = {
            str(entry.get("id")): entry
            for entry in mybatis_mapper.get("result_maps", [])
            if isinstance(entry, dict) and isinstance(entry.get("id"), str)
        }
        for statement in mybatis_mapper.get("statements", []):
            if not isinstance(statement, dict):
                continue
            statement_name = str(statement.get("id") or "")
            tables = [str(table).lower() for table in statement.get("tables", []) if isinstance(table, str) and table]
            if not tables:
                continue
            mapped_columns: set[str] = set()
            mapped_properties: set[str] = set()
            mapped_column_types: dict[str, str] = {}
            mapped_property_types: dict[str, str] = {}
            result_map_id = statement.get("result_map")
            if isinstance(result_map_id, str) and result_map_id:
                result_map = result_maps_by_id.get(result_map_id)
                if isinstance(result_map, dict):
                    mapped_columns.update(str(item).lower() for item in result_map.get("mapped_columns", []) if isinstance(item, str) and item)
                    mapped_properties.update(str(item).lower() for item in result_map.get("mapped_properties", []) if isinstance(item, str) and item)
                    class_columns, class_properties, class_column_types, class_property_types = collect_class_mapped_fields(resolve_class(result_map.get("type")))
                    mapped_columns.update(class_columns)
                    mapped_properties.update(class_properties)
                    mapped_column_types.update(class_column_types)
                    mapped_property_types.update(class_property_types)
            result_type = statement.get("result_type")
            class_columns, class_properties, class_column_types, class_property_types = collect_class_mapped_fields(resolve_class(result_type))
            mapped_columns.update(class_columns)
            mapped_properties.update(class_properties)
            mapped_column_types.update(class_column_types)
            mapped_property_types.update(class_property_types)
            for table_name in tables:
                entry = mappings_by_table.setdefault(
                    table_name,
                    {
                        "table_name": table_name,
                        "columns": set(),
                        "properties": set(),
                        "column_types": {},
                        "property_types": {},
                        "mappers": set(),
                        "statements": set(),
                    },
                )
                entry["columns"].update(mapped_columns)
                entry["properties"].update(mapped_properties)
                entry["column_types"].update(mapped_column_types)
                entry["property_types"].update(mapped_property_types)
                entry["mappers"].add(mapper_name)
                if statement_name:
                    entry["statements"].add(f"{mapper_name}.{statement_name}")
    return mappings_by_table


def check_brownfield_baseline_truthfulness(
    feature_dir: Path,
    feature_name: str,
    design_pack_dir: Path,
    *,
    risk_tier: str = "low",
    strict: bool = False,
    affected_components: list[str] | None = None,
) -> tuple[list[str], list[str], list[str], dict[str, object]]:
    checks: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    affected_component_set = {item for item in (affected_components or []) if item}

    baseline_dir = get_active_baseline_dir(create=True, migrate_legacy=True)
    module_map_path = baseline_dir / "module-map.json"
    schema_context_path = baseline_dir / "schema-context.json"
    real_index_path = baseline_dir / "sdd-index-real.json"
    evidence = {
        "module_map": baseline_file_evidence(module_map_path, default_level="L2", default_confidence="medium"),
        "schema_context": baseline_file_evidence(schema_context_path, default_level="L2", default_confidence="medium"),
    }

    source_warnings, source_errors, source_metadata = validate_schema_context_source(
        schema_context_path,
        risk_tier=risk_tier,
        strict=strict,
    )
    warnings.extend(source_warnings)
    errors.extend(source_errors)
    evidence["schema_context"].update(source_metadata)
    schema_signature_warnings, schema_signature_errors, schema_signature = validate_schema_context_signature(
        schema_context_path,
        attachment_path=DEFAULT_ATTACHMENT_PATH,
        strict=strict,
    )
    warnings.extend(schema_signature_warnings)
    errors.extend(schema_signature_errors)
    evidence["schema_context"].update(schema_signature)
    module_quality_warnings, module_quality_errors, module_quality = validate_module_map_quality(
        module_map_path,
        strict=strict,
    )
    warnings.extend(module_quality_warnings)
    errors.extend(module_quality_errors)
    evidence["module_map"].update(module_quality)
    attachment_warnings, attachment_errors, attachment_metadata = validate_attached_project_signature(
        module_map_path,
        attachment_path=DEFAULT_ATTACHMENT_PATH,
        strict=strict,
    )
    warnings.extend(attachment_warnings)
    errors.extend(attachment_errors)
    evidence["module_map"].update(attachment_metadata)
    module_fresh_warnings, module_fresh_errors, module_freshness = validate_baseline_freshness(
        "module-map",
        module_map_path,
        strict=strict,
    )
    schema_fresh_warnings, schema_fresh_errors, schema_freshness = validate_baseline_freshness(
        "schema-context",
        schema_context_path,
        strict=strict,
    )
    warnings.extend(module_fresh_warnings + schema_fresh_warnings)
    errors.extend(module_fresh_errors + schema_fresh_errors)
    evidence["module_map"].update(module_freshness)
    evidence["schema_context"].update(schema_freshness)

    design_path = detect_latest_design_path(feature_dir)
    design_text = design_path.read_text(encoding="utf-8", errors="ignore") if design_path.exists() else ""

    module_map = read_json_file(module_map_path, {})
    module_classes: set[str] = set()
    if isinstance(module_map, dict):
        for item in module_map.get("classes", []):
            if not isinstance(item, dict):
                continue
            if not matches_affected_components(item, affected_component_set):
                continue
            for key in ("simple_name", "class_name", "display_name", "fqn"):
                value = item.get(key)
                if isinstance(value, str) and value:
                    module_classes.add(value.split(".")[-1])

    participants = extract_design_participants(design_text)
    if participants:
        if not module_classes:
            errors.append(f"Brownfield 缺少可用 module-map 类快照: {module_map_path}")
        else:
            missing_classes = [name for name in participants if name not in module_classes]
            if missing_classes:
                errors.append(f"设计参与类未在 module-map.json 中找到: {', '.join(missing_classes)}")
            else:
                checks.append("Mermaid/classDiagram 参与类均存在于 module-map.json")
    elif has_new_domain_mermaid_fallback(design_text):
        checks.append("新领域模式下 Mermaid 参与类校验已按 fallback 说明豁免")
    else:
        warnings.append("未从设计文档中提取到 Mermaid participant 或 classDiagram 类名")

    openapi_operations = extract_operations_from_openapi(design_pack_dir / "接口契约.openapi.yaml")
    controller_checks, controller_errors = validate_openapi_controller_mapping(openapi_operations, module_map)
    checks.extend(controller_checks)
    errors.extend(controller_errors)

    openapi_paths = extract_paths_from_openapi(design_pack_dir / "接口契约.openapi.yaml")
    real_index = read_json_file(real_index_path, [])
    if openapi_paths and isinstance(real_index, list):
        already_implemented = any(
            isinstance(item, dict)
            and item.get("feature") in {feature_dir.name, feature_name}
            and bool(set(openapi_paths) & {str(path) for path in item.get("paths", []) if isinstance(path, str)})
            for item in real_index
        )
        conflicting_paths: list[str] = []
        if already_implemented:
            checks.append("当前设计已存在实现态 baseline 记录，跳过同路径历史实现态冲突阻断")
        else:
            for item in real_index:
                if not isinstance(item, dict) or item.get("feature") in {feature_dir.name, feature_name}:
                    continue
                existing_paths = {str(path) for path in item.get("paths", []) if isinstance(path, str)}
                conflicting_paths.extend(sorted(existing_paths & set(openapi_paths)))
            if conflicting_paths:
                errors.append(f"接口路径已存在于实现态 baseline: {', '.join(sorted(set(conflicting_paths)))}")
            else:
                checks.append("接口路径未与 sdd-index-real.json 中其他 feature 冲突")

    schema_context = read_json_file(schema_context_path, {})
    schema_tables: dict[str, dict[str, object]] = {}
    if isinstance(schema_context, dict):
        for table in schema_context.get("tables", []):
            if isinstance(table, dict) and isinstance(table.get("table_name"), str):
                if not matches_affected_components(table, affected_component_set):
                    continue
                table_name = str(table["table_name"])
                existing = schema_tables.get(table_name)
                if not isinstance(existing, dict):
                    schema_tables[table_name] = dict(table)
                    continue
                existing["columns"] = sorted(
                    set(existing.get("columns", [])) | set(table.get("columns", []))
                )
                existing["declared_columns"] = sorted(
                    set(existing.get("declared_columns", [])) | set(table.get("declared_columns", []))
                )
                existing["sql_columns"] = sorted(
                    set(existing.get("sql_columns", [])) | set(table.get("sql_columns", []))
                )
                existing["indexed_columns"] = sorted(
                    set(existing.get("indexed_columns", [])) | set(table.get("indexed_columns", []))
                )
                existing["sources"] = sorted(set(existing.get("sources", [])) | set(table.get("sources", [])))
                existing["column_details"] = list(existing.get("column_details", [])) + [
                    detail
                    for detail in table.get("column_details", [])
                    if isinstance(detail, dict) and detail not in existing.get("column_details", [])
                ]

    data_model_tables = extract_tables_from_data_model(design_pack_dir / "数据模型.md")
    data_model_fields = extract_table_fields_from_data_model(design_pack_dir / "数据模型.md")
    created_tables = extract_created_tables(design_pack_dir / "数据库变更.sql")
    jpa_entities_by_table = extract_jpa_entities_from_module_map(module_map, affected_component_set)
    mybatis_mappings_by_table = extract_mybatis_table_mappings_from_module_map(module_map, affected_component_set)
    if data_model_tables:
        missing_tables: list[str] = []
        for table_name in data_model_tables:
            if table_name in created_tables:
                continue
            table_meta = schema_tables.get(table_name)
            if not table_meta:
                missing_tables.append(table_name)
                continue
            sources = table_meta.get("sources", [])
            if isinstance(sources, list) and all(is_current_feature_source(source, feature_dir) for source in sources):
                missing_tables.append(table_name)
        if missing_tables:
            errors.append(
                "数据模型引用的表未在既有 schema-context 中找到，且未在数据库变更.sql 中 CREATE TABLE: "
                + ", ".join(sorted(set(missing_tables)))
            )
        else:
            checks.append("数据模型表名均可追溯到 schema-context 或明确 CREATE TABLE")

    if data_model_fields:
        missing_fields: list[str] = []
        type_mismatches: list[str] = []
        nullable_mismatches: list[str] = []
        missing_nullable: list[str] = []
        jpa_mapping_mismatches: list[str] = []
        mybatis_mapping_mismatches: list[str] = []
        mybatis_type_mismatches: list[str] = []
        data_model_field_specs = extract_table_field_specs_from_data_model(design_pack_dir / "数据模型.md")
        for table_name, fields in data_model_fields.items():
            if table_name in created_tables:
                continue
            table_meta = schema_tables.get(table_name)
            if not table_meta:
                continue
            existing_columns = {str(column).lower() for column in table_meta.get("columns", []) if isinstance(column, str)}
            column_details_by_name: dict[str, dict[str, object]] = {}
            for detail in table_meta.get("column_details", []):
                if isinstance(detail, dict) and isinstance(detail.get("name"), str):
                    column_name = str(detail["name"]).lower()
                    existing_columns.add(column_name)
                    column_details_by_name[column_name] = detail
            for field in fields:
                field_key = field.lower()
                if field_key not in existing_columns:
                    missing_fields.append(f"{table_name}.{field}")
                    continue
                field_spec = data_model_field_specs.get(table_name, {}).get(field, {})
                column_detail = column_details_by_name.get(field_key)
                if not isinstance(field_spec, dict) or not column_detail:
                    continue
                expected_type = normalize_schema_type(field_spec.get("type"))
                actual_type = normalize_schema_type(column_detail.get("type") or column_detail.get("data_type"))
                if expected_type and actual_type and expected_type != actual_type:
                    type_mismatches.append(
                        f"{table_name}.{field}: design={field_spec.get('type')}, schema={column_detail.get('type') or column_detail.get('data_type')}"
                    )
                if "nullable" in field_spec:
                    expected_nullable = parse_schema_nullable(field_spec.get("nullable"))
                    actual_nullable = parse_schema_nullable(column_detail.get("nullable"))
                    if actual_nullable is None:
                        missing_nullable.append(f"{table_name}.{field}")
                    elif expected_nullable is not None and expected_nullable != actual_nullable:
                        nullable_mismatches.append(
                            f"{table_name}.{field}: design={expected_nullable}, schema={actual_nullable}"
                        )
            jpa_entity = jpa_entities_by_table.get(table_name)
            if jpa_entity:
                mapped_columns = set(jpa_entity.get("columns", set()))
                mapped_fields = set(jpa_entity.get("fields", set()))
                entity_classes = sorted(str(item) for item in jpa_entity.get("entity_classes", set()))
                for field in fields:
                    field_key = field.lower()
                    if field_key in mapped_columns or field_key in mapped_fields:
                        continue
                    jpa_mapping_mismatches.append(
                        f"{table_name}.{field}: entity={', '.join(entity_classes)}"
                    )
            mybatis_mapping = mybatis_mappings_by_table.get(table_name.lower())
            if mybatis_mapping:
                mapped_columns = set(mybatis_mapping.get("columns", set()))
                mapped_properties = set(mybatis_mapping.get("properties", set()))
                mapped_column_types = dict(mybatis_mapping.get("column_types", {}))
                mapped_property_types = dict(mybatis_mapping.get("property_types", {}))
                statements = sorted(str(item) for item in mybatis_mapping.get("statements", set()))
                for field in fields:
                    field_key = field.lower()
                    if field_key in mapped_columns or field_key in mapped_properties:
                        field_spec = data_model_field_specs.get(table_name, {}).get(field, {})
                        expected_type = normalize_schema_type(field_spec.get("type")) if isinstance(field_spec, dict) else None
                        actual_type = mapped_column_types.get(field_key) or mapped_property_types.get(field_key)
                        if expected_type and actual_type and expected_type != actual_type:
                            mybatis_type_mismatches.append(
                                f"{table_name}.{field}: design={field_spec.get('type')}, mybatis={actual_type}, statements={', '.join(statements)}"
                            )
                        continue
                    mybatis_mapping_mismatches.append(
                        f"{table_name}.{field}: statements={', '.join(statements)}"
                    )
        if missing_fields:
            errors.append("数据模型引用的字段未在 schema-context 中找到: " + ", ".join(sorted(set(missing_fields))))
        if type_mismatches:
            errors.append("字段类型与 schema-context 不一致: " + ", ".join(sorted(set(type_mismatches))))
        if nullable_mismatches:
            errors.append("字段 nullable 与 schema-context 不一致: " + ", ".join(sorted(set(nullable_mismatches))))
        if missing_nullable:
            errors.append("字段 nullable 未在 schema-context 中声明: " + ", ".join(sorted(set(missing_nullable))))
        if jpa_mapping_mismatches:
            errors.append("数据模型字段未映射到 JPA Entity/@Column: " + ", ".join(sorted(set(jpa_mapping_mismatches))))
        if mybatis_mapping_mismatches:
            errors.append("数据模型字段未映射到 MyBatis resultMap/resultType: " + ", ".join(sorted(set(mybatis_mapping_mismatches))))
        if mybatis_type_mismatches:
            errors.append("MyBatis resultMap/resultType 字段类型与数据模型不一致: " + ", ".join(sorted(set(mybatis_type_mismatches))))
        if not missing_fields and not type_mismatches and not nullable_mismatches and not missing_nullable and not jpa_mapping_mismatches and not mybatis_mapping_mismatches and not mybatis_type_mismatches:
            checks.append("数据模型字段、类型与 nullable 均可追溯到 schema-context")

    return checks, warnings, errors, evidence


def write_gate2_report(feature_dir: Path, feature_name: str, report: dict[str, object]) -> Path:
    design_path = detect_latest_design_path(feature_dir)
    reports_dir = reports_dir_for_design(feature_dir, design_path)
    result = "PASS" if report.get("status") == "OK" else "FAIL"
    return write_gate_section(
        reports_dir,
        gate_name="gate2",
        feature_name=feature_name,
        design_version=design_path.name,
        payload={
            "result": result,
            "checks": report.get("checks", []),
            "warnings": report.get("warnings", []),
            "errors": report.get("errors", []),
            "evidence": report.get("evidence", {}),
            "truthfulness_report": report,
        },
    )


def check_truthfulness(feature_path: str, *, strict: bool = False) -> dict[str, object]:
    feature_dir = resolve_feature_dir(feature_path)
    brief_file = feature_dir / "feature-brief.md"

    if not brief_file.exists():
        return {"status": "FAIL", "reason": f"Missing feature-brief.md in {feature_path}", "errors": []}

    brief_content = brief_file.read_text(encoding="utf-8")
    feature_name = extract_feature_name(brief_content, feature_dir)
    project_mode = extract_project_mode(brief_content)
    risk_tier = extract_risk_tier(brief_content)
    affected_components = extract_affected_components(brief_content)
    strict_mode = is_strict_enabled(strict)
    design_path = detect_latest_design_path(feature_dir)
    reports_dir = reports_dir_for_design(feature_dir, design_path)
    design_pack_dir = resolve_design_pack_dir(feature_dir, reports_dir)
    checks: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []

    if project_mode == "greenfield":
        bootstrap_checks, bootstrap_errors = check_bootstrap_artifacts(feature_dir)
        checks.extend(bootstrap_checks)
        errors.extend(bootstrap_errors)
        if bootstrap_errors:
            report = {
                "feature": feature_dir.name,
                "project_mode": project_mode,
                "status": "FAIL",
                "checks": checks,
                "warnings": warnings,
                "errors": errors,
                "reason": "greenfield bootstrap 校验失败",
            }
            write_gate2_report(feature_dir, feature_name, report)
            return report
    else:
        brownfield_checks, brownfield_warnings, brownfield_errors, brownfield_evidence = check_brownfield_baseline_truthfulness(
            feature_dir,
            feature_name,
            design_pack_dir,
            risk_tier=risk_tier,
            strict=strict_mode,
            affected_components=affected_components,
        )
        checks.extend(brownfield_checks)
        warnings.extend(brownfield_warnings)
        errors.extend(brownfield_errors)
    if project_mode == "greenfield":
        brownfield_evidence = {}

    req_ids = extract_req_ids(brief_content)
    if not req_ids:
        errors.append("No REQ-IDs found in feature-brief.md")
        report = {
            "feature": feature_dir.name,
            "project_mode": project_mode,
            "status": "FAIL",
            "checks": checks,
            "warnings": warnings,
            "errors": errors,
            "reason": "No REQ-IDs found in feature-brief.md",
        }
        write_gate2_report(feature_dir, feature_name, report)
        return report

    coverage_result = collect_design_pack_coverage(design_pack_dir, req_ids)
    coverage = coverage_result["coverage"]
    file_issues = coverage_result["file_issues"]
    errors.extend(str(item) for item in coverage_result["errors"])

    missing_reqs = [req for req, files in coverage.items() if not files]  # type: ignore[union-attr]
    if not missing_reqs:
        checks.append("所有 REQ-ID 均已被 design-pack 覆盖")

    report = {
        "feature": feature_dir.name,
        "project_mode": project_mode,
        "risk_tier": risk_tier,
        "affected_components": affected_components,
        "strict": strict_mode,
        "total_requirements": len(req_ids),
        "covered_requirements": len(req_ids) - len(missing_reqs),
        "missing_requirements": missing_reqs,
        "coverage_detail": coverage,
        "content_issues": file_issues,
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
        "evidence": {
            "design": {
                "source": str(design_path),
                "hash": hash_file(design_path),
                "evidence_level": "L3",
                "confidence": "medium",
            },
            "design_pack": {
                "source": str(design_pack_dir),
                "hash": hash_tree(design_pack_dir),
                "evidence_level": "L3",
                "confidence": "medium",
            },
            **brownfield_evidence,
        },
        "status": "FAIL" if errors else "OK",
    }
    write_gate2_report(feature_dir, feature_name, report)
    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("feature_path")
    parser.add_argument("--strict", action="store_true", help="严格模式：低可信或 fallback 事实源阻断")
    args = parser.parse_args()

    result = check_truthfulness(args.feature_path, strict=args.strict)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["status"] == "FAIL":
        sys.exit(1)
