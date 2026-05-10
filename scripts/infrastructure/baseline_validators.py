#!/usr/bin/env python3
"""
Shared baseline freshness and signature validators.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from domain.attached_project import DEFAULT_ATTACHMENT_PATH, resolve_module_map_scan_settings, source_signature
from refresh_schema_context import resolve_schema_context_sources, source_signature as schema_context_source_signature


def parse_ttl(value: object) -> timedelta | None:
    if isinstance(value, (int, float)):
        return timedelta(seconds=float(value))
    if not isinstance(value, str) or not value:
        return None
    if value.isdigit():
        return timedelta(seconds=int(value))
    import re

    match = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", value)
    if not match:
        return None
    return timedelta(
        days=int(match.group(1) or 0),
        hours=int(match.group(2) or 0),
        minutes=int(match.group(3) or 0),
        seconds=int(match.group(4) or 0),
    )


def parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def validate_baseline_freshness(label: str, path: Path, *, strict: bool) -> tuple[list[str], list[str], dict[str, object]]:
    warnings: list[str] = []
    errors: list[str] = []
    metadata: dict[str, object] = {"freshness": "unknown"}
    if not path.exists():
        return warnings, errors, metadata
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return warnings, errors, metadata
    if not isinstance(payload, dict):
        return warnings, errors, metadata

    generated_at = parse_datetime(payload.get("generated_at"))
    ttl = parse_ttl(payload.get("ttl"))
    metadata["generated_at"] = payload.get("generated_at")
    metadata["ttl"] = payload.get("ttl")
    if generated_at is None or ttl is None:
        return warnings, errors, metadata

    expires_at = generated_at + ttl
    metadata["expires_at"] = expires_at.isoformat()
    metadata["freshness"] = "stale" if datetime.now(timezone.utc) > expires_at else "fresh"
    if metadata["freshness"] == "stale":
        message = f"{label} baseline is stale: generated_at={generated_at.isoformat()}, ttl={payload.get('ttl')}"
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
    try:
        module_map = json.loads(module_map_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return warnings, errors, metadata
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
        message = "attached project configuration has changed; module-map baseline needs refresh"
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
    try:
        schema_context = json.loads(schema_context_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return warnings, errors, metadata
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
        message = "schema-context configuration has changed; schema-context baseline needs refresh"
        if strict:
            errors.append(message)
        else:
            warnings.append(message)
    return warnings, errors, metadata

