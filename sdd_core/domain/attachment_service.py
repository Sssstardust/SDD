#!/usr/bin/env python3
"""
Domain services and mapping functions for target project attachments (FIX-017).
"""

from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path
from typing import Any

from sdd_core.domain.language_profiles import normalize_language
from sdd_core.domain.design_common import unique_preserve
from sdd_core.domain.attachment_domain import (
    ROOT,
    DEFAULT_ATTACHMENT_PATH,
    COMPONENT_RESERVED_FIELDS,
    normalize_path,
    normalize_root_list,
    default_scan_roots,
    default_schema_roots,
    build_attachment_project_id,
    build_attachment_profile_name,
)


def build_component_payload(
    *,
    component_id: str,
    project_root: Path | str | None = None,
    name: str | None = None,
    scan_roots: list[Path | str] | None = None,
    design_roots: list[Path | str] | None = None,
    schema_roots: list[Path | str] | None = None,
    language: str | None = None,
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    project_root_path = Path(project_root).resolve() if project_root is not None else None
    resolved_language = normalize_language(language)
    effective_scan_roots = scan_roots or (default_scan_roots(project_root_path, resolved_language) if project_root_path else [])
    effective_design_roots = design_roots or [ROOT / "specs"]
    effective_schema_roots = schema_roots or (default_schema_roots(project_root_path, resolved_language) if project_root_path else [])
    payload: dict[str, Any] = dict(extra_fields or {})
    payload.update(
        {
            "component_id": component_id,
            "name": name or component_id,
            "language": resolved_language,
            "scan_roots": [normalize_path(path) for path in effective_scan_roots],
            "design_roots": [normalize_path(path) for path in effective_design_roots],
            "schema_roots": [normalize_path(path) for path in effective_schema_roots],
        }
    )
    if project_root_path is not None:
        payload["project_root"] = normalize_path(project_root_path)
    else:
        payload.pop("project_root", None)
    return payload


def normalize_components(raw_components: object) -> list[dict[str, Any]]:
    if not isinstance(raw_components, list):
        return []
    normalized: list[dict[str, Any]] = []
    for index, raw_component in enumerate(raw_components, start=1):
        if not isinstance(raw_component, dict):
            continue
        component_id = str(raw_component.get("component_id") or raw_component.get("name") or f"component-{index}").strip()
        if not component_id:
            continue
        extra_fields = {
            key: value
            for key, value in raw_component.items()
            if key not in COMPONENT_RESERVED_FIELDS
        }
        normalized.append(
            build_component_payload(
                component_id=component_id,
                project_root=raw_component.get("project_root"),
                name=str(raw_component.get("name") or component_id),
                scan_roots=list(raw_component.get("scan_roots", [])) if isinstance(raw_component.get("scan_roots"), list) else None,
                design_roots=list(raw_component.get("design_roots", [])) if isinstance(raw_component.get("design_roots"), list) else None,
                schema_roots=list(raw_component.get("schema_roots", [])) if isinstance(raw_component.get("schema_roots"), list) else None,
                language=str(raw_component.get("language")) if raw_component.get("language") is not None else None,
                extra_fields=extra_fields,
            )
        )
    return normalized


def collect_component_roots(components: list[dict[str, Any]], field_name: str) -> list[str]:
    collected: list[str] = []
    for component in components:
        values = component.get(field_name)
        if isinstance(values, list):
            collected.extend(str(item) for item in values if isinstance(item, str))
    return unique_preserve(collected)


def normalize_attachment_payload(payload: dict[str, Any]) -> dict[str, Any]:
    components = normalize_components(payload.get("components"))
    normalized: dict[str, Any] = dict(payload)
    normalized["components"] = components
    project_root = normalized.get("project_root")
    if isinstance(project_root, str) and project_root:
        normalized["project_root"] = normalize_path(project_root)
    elif len(components) == 1 and isinstance(components[0].get("project_root"), str) and components[0].get("project_root"):
        normalized["project_root"] = str(components[0]["project_root"])
    else:
        normalized.pop("project_root", None)

    normalized["scan_roots"] = unique_preserve(normalize_root_list(normalized.get("scan_roots")))
    normalized["design_roots"] = unique_preserve(normalize_root_list(normalized.get("design_roots")))
    normalized["schema_roots"] = unique_preserve(normalize_root_list(normalized.get("schema_roots")))

    if components:
        normalized["scan_roots"] = unique_preserve(
            list(normalized["scan_roots"]) + collect_component_roots(components, "scan_roots")
        )
        normalized["design_roots"] = unique_preserve(
            list(normalized["design_roots"]) + collect_component_roots(components, "design_roots")
        )
        normalized["schema_roots"] = unique_preserve(
            list(normalized["schema_roots"]) + collect_component_roots(components, "schema_roots")
        )
    return normalized


def component_id_for_path(
    path: Path | str | None,
    source_settings: dict[str, Any] | None = None,
    *,
    preferred_fields: tuple[str, ...] = ("scan_roots", "design_roots", "schema_roots"),
) -> str:
    if path is None:
        return ""
    value = Path(path)
    candidate = value.name or value.stem
    if candidate and candidate != ".":
        normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", candidate).strip("-._")
        if normalized:
            return normalized
    if isinstance(source_settings, dict):
        for field in preferred_fields:
            roots = source_settings.get(field)
            if isinstance(roots, list) and roots:
                first = roots[0]
                if isinstance(first, str) and first:
                    candidate = Path(first).stem or Path(first).name
                    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", candidate).strip("-._")
                    if normalized:
                        return normalized
    return "default"


def resolve_module_map_scan_settings(
    *,
    attachment_path: Path = DEFAULT_ATTACHMENT_PATH,
    scan_roots: list[Path | str] | None = None,
    design_roots: list[Path | str] | None = None,
    schema_roots: list[Path | str] | None = None,
    project_root: Path | str | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    from sdd_core.domain.attached_project import load_attachment_config
    attachment = load_attachment_config(attachment_path, profile=profile) or {}
    resolved_scan_roots = scan_roots
    if resolved_scan_roots is None and isinstance(attachment.get("scan_roots"), list):
        resolved_scan_roots = [Path(str(item)) for item in attachment.get("scan_roots", []) if isinstance(item, str) and item]
    resolved_design_roots = design_roots
    if resolved_design_roots is None and isinstance(attachment.get("design_roots"), list):
        resolved_design_roots = [Path(str(item)) for item in attachment.get("design_roots", []) if isinstance(item, str) and item]
    resolved_schema_roots = schema_roots
    if resolved_schema_roots is None and isinstance(attachment.get("schema_roots"), list):
        resolved_schema_roots = [Path(str(item)) for item in attachment.get("schema_roots", []) if isinstance(item, str) and item]
    resolved_project_root = project_root
    if resolved_project_root is None and isinstance(attachment.get("project_root"), str) and attachment.get("project_root"):
        resolved_project_root = Path(str(attachment.get("project_root")))
    payload = {
        "source": "attachment",
        "attachment_path": str(attachment_path),
        "profile": profile or attachment.get("profile"),
        "scan_roots": [normalize_path(path) for path in (resolved_scan_roots or [])],
        "design_roots": [normalize_path(path) for path in (resolved_design_roots or [])],
        "schema_roots": [normalize_path(path) for path in (resolved_schema_roots or [])],
        "project_root": normalize_path(resolved_project_root) if resolved_project_root is not None else None,
    }
    return payload


def source_signature(payload: dict[str, Any] | None = None) -> str:
    data = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def build_attachment_payload(
    *,
    project_root: Path | str | None = None,
    name: str | None = None,
    scan_roots: list[Path | str] | None = None,
    design_roots: list[Path | str] | None = None,
    schema_roots: list[Path | str] | None = None,
    components: list[dict[str, Any]] | None = None,
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = dict(extra_fields or {})
    payload["name"] = name or payload.get("name") or "attached-project"
    if project_root is not None:
        payload["project_root"] = normalize_path(project_root)
    elif isinstance(payload.get("project_root"), str):
        payload["project_root"] = normalize_path(payload["project_root"])
    if scan_roots is not None:
        payload["scan_roots"] = [normalize_path(path) for path in scan_roots]
    if design_roots is not None:
        payload["design_roots"] = [normalize_path(path) for path in design_roots]
    if schema_roots is not None:
        payload["schema_roots"] = [normalize_path(path) for path in schema_roots]
    payload["components"] = normalize_components(components or payload.get("components"))
    payload["project_id"] = build_attachment_project_id(payload)
    payload["profile"] = build_attachment_profile_name(payload)
    return normalize_attachment_payload(payload)


def normalize_attachment_json(payload: object) -> dict[str, Any]:
    return normalize_attachment_payload(payload if isinstance(payload, dict) else {})
