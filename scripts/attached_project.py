#!/usr/bin/env python3
"""
attached_project.py

维护 SDD 工具仓库附着到目标项目时的扫描配置。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ATTACHMENT_PATH = ROOT / ".spec" / "attached-project.json"
COMPONENT_ROOT_FIELDS = {"scan_roots", "design_roots", "schema_roots"}
COMPONENT_RESERVED_FIELDS = {"component_id", "name", "project_root", *COMPONENT_ROOT_FIELDS}
ATTACHMENT_ROOT_FIELDS = {"scan_roots", "design_roots", "schema_roots"}
ATTACHMENT_RESERVED_FIELDS = {"name", "project_root", "components", *ATTACHMENT_ROOT_FIELDS}


def normalize_path(value: Path | str) -> str:
    return str(Path(value).resolve())


def normalize_candidate_path(value: Path | str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate.resolve()
    return (ROOT / candidate).resolve()


def normalize_root_list(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(item) for item in values if isinstance(item, str)]


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def default_scan_roots(project_root: Path) -> list[Path]:
    return [
        project_root / "src" / "main" / "java",
        project_root / "src" / "test" / "java",
    ]


def default_schema_roots(project_root: Path) -> list[Path]:
    return [
        project_root / "src" / "main" / "resources",
        project_root / "src" / "test" / "resources",
        project_root / "db",
        project_root / "sql",
    ]


def build_component_payload(
    *,
    component_id: str,
    project_root: Path | str | None = None,
    name: str | None = None,
    scan_roots: list[Path | str] | None = None,
    design_roots: list[Path | str] | None = None,
    schema_roots: list[Path | str] | None = None,
    extra_fields: dict[str, object] | None = None,
) -> dict[str, object]:
    project_root_path = Path(project_root).resolve() if project_root is not None else None
    effective_scan_roots = scan_roots or (default_scan_roots(project_root_path) if project_root_path else [])
    effective_design_roots = design_roots or [ROOT / "specs"]
    effective_schema_roots = schema_roots or (default_schema_roots(project_root_path) if project_root_path else [])
    payload: dict[str, object] = dict(extra_fields or {})
    payload.update(
        {
        "component_id": component_id,
        "name": name or component_id,
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


def normalize_components(raw_components: object) -> list[dict[str, object]]:
    if not isinstance(raw_components, list):
        return []
    normalized: list[dict[str, object]] = []
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
                extra_fields=extra_fields,
            )
        )
    return normalized


def collect_component_roots(components: list[dict[str, object]], field_name: str) -> list[str]:
    collected: list[str] = []
    for component in components:
        values = component.get(field_name)
        if isinstance(values, list):
            collected.extend(str(item) for item in values if isinstance(item, str))
    return dedupe_preserve_order(collected)


def normalize_attachment_payload(payload: dict[str, object]) -> dict[str, object]:
    components = normalize_components(payload.get("components"))
    normalized: dict[str, object] = dict(payload)
    normalized["components"] = components
    project_root = normalized.get("project_root")
    if isinstance(project_root, str) and project_root:
        normalized["project_root"] = normalize_path(project_root)
    elif len(components) == 1 and isinstance(components[0].get("project_root"), str) and components[0].get("project_root"):
        normalized["project_root"] = str(components[0]["project_root"])
    else:
        normalized.pop("project_root", None)

    normalized["scan_roots"] = dedupe_preserve_order(normalize_root_list(normalized.get("scan_roots")))
    normalized["design_roots"] = dedupe_preserve_order(normalize_root_list(normalized.get("design_roots")))
    normalized["schema_roots"] = dedupe_preserve_order(normalize_root_list(normalized.get("schema_roots")))

    if components:
        normalized["scan_roots"] = dedupe_preserve_order(
            list(normalized["scan_roots"]) + collect_component_roots(components, "scan_roots")
        )
        normalized["design_roots"] = dedupe_preserve_order(
            list(normalized["design_roots"]) + collect_component_roots(components, "design_roots")
        )
        normalized["schema_roots"] = dedupe_preserve_order(
            list(normalized["schema_roots"]) + collect_component_roots(components, "schema_roots")
        )
    return normalized


def build_attachment_payload(
    *,
    project_root: Path | str | None = None,
    name: str | None = None,
    scan_roots: list[Path | str] | None = None,
    design_roots: list[Path | str] | None = None,
    schema_roots: list[Path | str] | None = None,
    components: list[dict[str, object]] | None = None,
    extra_fields: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = dict(extra_fields or {})
    normalized_components = normalize_components(components if components is not None else payload.get("components"))
    project_root_value = project_root if project_root is not None else payload.get("project_root")
    project_root_path = Path(project_root_value).resolve() if project_root_value is not None else None
    if project_root_path is None and len(normalized_components) == 1:
        component_project_root = normalized_components[0].get("project_root")
        if isinstance(component_project_root, str) and component_project_root:
            project_root_path = Path(component_project_root)
    if project_root_path is None and not normalized_components:
        raise ValueError("project_root or components is required")

    effective_scan_roots = (
        scan_roots
        if scan_roots is not None
        else normalize_root_list(payload.get("scan_roots")) or (default_scan_roots(project_root_path) if project_root_path else [])
    )
    effective_design_roots = (
        design_roots
        if design_roots is not None
        else normalize_root_list(payload.get("design_roots")) or [ROOT / "specs"]
    )
    effective_schema_roots = (
        schema_roots
        if schema_roots is not None
        else normalize_root_list(payload.get("schema_roots")) or (default_schema_roots(project_root_path) if project_root_path else [])
    )

    default_name = "attached-project"
    if project_root_path is not None:
        default_name = project_root_path.name
    elif len(normalized_components) == 1:
        default_name = str(normalized_components[0].get("name") or normalized_components[0].get("component_id") or default_name)

    payload.update(
        {
        "name": name or str(payload.get("name") or default_name),
        "scan_roots": [normalize_path(path) for path in effective_scan_roots],
        "design_roots": [normalize_path(path) for path in effective_design_roots],
        "schema_roots": [normalize_path(path) for path in effective_schema_roots],
        }
    )
    if project_root_path is not None:
        payload["project_root"] = normalize_path(project_root_path)
    else:
        payload.pop("project_root", None)
    if normalized_components:
        payload["components"] = normalized_components
    else:
        payload.pop("components", None)
    return normalize_attachment_payload(payload)


def save_attachment_config(payload: dict[str, object], attachment_path: Path = DEFAULT_ATTACHMENT_PATH) -> Path:
    attachment_path.parent.mkdir(parents=True, exist_ok=True)
    attachment_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return attachment_path


def load_attachment_config(attachment_path: Path = DEFAULT_ATTACHMENT_PATH) -> dict[str, object] | None:
    if not attachment_path.exists():
        return None
    payload = json.loads(attachment_path.read_text(encoding="utf-8"))
    return normalize_attachment_payload(payload) if isinstance(payload, dict) else None


def load_attachment_seed(seed_path: Path) -> dict[str, object]:
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return normalize_attachment_payload({"components": payload})
    if isinstance(payload, dict):
        return normalize_attachment_payload(payload)
    raise ValueError(f"unsupported attachment seed format: {seed_path}")


def match_component_by_path(
    path_value: Path | str | None,
    attachment: dict[str, object],
    *,
    preferred_fields: tuple[str, ...] = ("scan_roots", "design_roots", "schema_roots"),
) -> dict[str, object] | None:
    components = normalize_components(attachment.get("components"))
    if not components:
        return None
    if path_value is None:
        return components[0] if len(components) == 1 else None

    candidate_path = normalize_candidate_path(path_value)
    best_match: tuple[int, int, dict[str, object]] | None = None
    for component in components:
        roots: list[tuple[int, str]] = []
        for field_priority, field_name in enumerate(preferred_fields):
            values = component.get(field_name)
            if isinstance(values, list):
                roots.extend((field_priority, str(item)) for item in values if isinstance(item, str))
        project_root = component.get("project_root")
        if isinstance(project_root, str) and project_root:
            roots.append((len(preferred_fields), project_root))

        for field_priority, root in roots:
            root_path = normalize_candidate_path(root)
            try:
                relative = candidate_path.relative_to(root_path)
            except ValueError:
                continue
            score = (len(root_path.parts), -field_priority)
            if best_match is None or score > (best_match[0], best_match[1]):
                best_match = (score[0], score[1], component)
            if not relative.parts:
                break

    if best_match is not None:
        return best_match[2]
    return components[0] if len(components) == 1 else None


def component_id_for_path(
    path_value: Path | str | None,
    attachment: dict[str, object],
    *,
    preferred_fields: tuple[str, ...] = ("scan_roots", "design_roots", "schema_roots"),
) -> str | None:
    component = match_component_by_path(path_value, attachment, preferred_fields=preferred_fields)
    component_id = component.get("component_id") if isinstance(component, dict) else None
    return str(component_id) if isinstance(component_id, str) and component_id else None


def source_signature(scan_settings: dict[str, object]) -> str:
    components = normalize_components(scan_settings.get("components"))
    relevant = {
        "project_root": scan_settings.get("project_root"),
        "scan_roots": scan_settings.get("scan_roots", []),
        "design_roots": scan_settings.get("design_roots", []),
        "source": scan_settings.get("source"),
        "components": [
            {
                "component_id": component.get("component_id"),
                "project_root": component.get("project_root"),
                "scan_roots": component.get("scan_roots", []),
                "design_roots": component.get("design_roots", []),
                "schema_roots": component.get("schema_roots", []),
            }
            for component in components
        ],
    }
    content = json.dumps(relevant, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def resolve_module_map_scan_settings(
    *,
    attachment_path: Path = DEFAULT_ATTACHMENT_PATH,
    scan_roots: list[Path | str] | None,
    design_roots: list[Path | str] | None,
    project_root: Path | str | None,
) -> dict[str, object]:
    if project_root is not None:
        payload = build_attachment_payload(
            project_root=project_root,
            scan_roots=scan_roots,
            design_roots=design_roots,
        )
        payload["source"] = "project_root"
        return payload

    if scan_roots or design_roots:
        payload: dict[str, object] = {
            "name": "cli-scan-settings",
            "project_root": None,
            "scan_roots": [normalize_path(path) for path in (scan_roots or [])],
            "design_roots": [normalize_path(path) for path in (design_roots or [ROOT / "specs"])],
            "source": "cli",
        }
        return normalize_attachment_payload(payload)

    attachment = load_attachment_config(attachment_path)
    if attachment is not None:
        return {
            **attachment,
            "source": "attachment",
        }

    return normalize_attachment_payload(
        {
        "name": "current-workspace",
        "project_root": normalize_path(ROOT),
        "scan_roots": [normalize_path(ROOT / "src" / "main" / "java"), normalize_path(ROOT / "src" / "test" / "java")],
        "design_roots": [normalize_path(ROOT / "specs")],
        "schema_roots": [normalize_path(ROOT / "src" / "main" / "resources"), normalize_path(ROOT / "sql"), normalize_path(ROOT / "db")],
        "source": "default",
        }
    )
