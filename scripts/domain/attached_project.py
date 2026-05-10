#!/usr/bin/env python3
"""
Domain-level attachment payload normalization helpers.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from infrastructure.concurrency import atomic_write_text, path_lock

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ATTACHMENT_PATH = ROOT / ".spec" / "attached-project.json"
DEFAULT_ATTACHMENTS_DIR = DEFAULT_ATTACHMENT_PATH.parent / "attachments"
DEFAULT_ATTACHMENT_REGISTRY_PATH = DEFAULT_ATTACHMENTS_DIR / "registry.json"
DEFAULT_WORKSPACE_PATH = DEFAULT_ATTACHMENT_PATH.parent / "workspace.json"
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


def attachments_dir_for(attachment_path: Path = DEFAULT_ATTACHMENT_PATH) -> Path:
    effective = attachment_path if attachment_path.is_absolute() else (ROOT / attachment_path).resolve()
    return effective.parent / "attachments"


def attachment_profiles_dir_for(attachment_path: Path = DEFAULT_ATTACHMENT_PATH) -> Path:
    return attachments_dir_for(attachment_path) / "profiles"


def attachment_registry_path_for(attachment_path: Path = DEFAULT_ATTACHMENT_PATH) -> Path:
    return attachments_dir_for(attachment_path) / "registry.json"


def workspace_path_for(attachment_path: Path = DEFAULT_ATTACHMENT_PATH) -> Path:
    effective = attachment_path if attachment_path.is_absolute() else (ROOT / attachment_path).resolve()
    return effective.parent / "workspace.json"


def write_attachment_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def build_workspace_payload(attachment_path: Path = DEFAULT_ATTACHMENT_PATH) -> dict[str, object]:
    profiles = list_attachment_profiles(attachment_path)
    active = next((item for item in profiles if item.get("active") is True), None)
    return {
        "version": 1,
        "active_profile": active.get("profile") if isinstance(active, dict) else None,
        "active_project_id": active.get("project_id") if isinstance(active, dict) else None,
        "profiles": profiles,
    }


def refresh_workspace_file(attachment_path: Path = DEFAULT_ATTACHMENT_PATH) -> Path:
    path = workspace_path_for(attachment_path)
    payload = build_workspace_payload(attachment_path)
    return write_attachment_json(path, payload)


def attachment_store_lock_path(attachment_path: Path = DEFAULT_ATTACHMENT_PATH) -> Path:
    effective = attachment_path if attachment_path.is_absolute() else (ROOT / attachment_path).resolve()
    return attachments_dir_for(effective)


def sanitize_profile_name(value: str) -> str:
    normalized = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value.strip().lower())
    normalized = normalized.strip("-._")
    return normalized or "default"


def sanitize_bucket_name(value: str) -> str:
    normalized = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value.strip().lower())
    normalized = normalized.strip("-._")
    return normalized or "attached-project"


def build_profile_project_id(name: str, project_root: str) -> str:
    suffix = hashlib.sha1(project_root.encode("utf-8")).hexdigest()[:8]
    return f"{sanitize_bucket_name(name)}-{suffix}"


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


def build_attachment_project_id(payload: dict[str, object]) -> str:
    explicit = payload.get("project_id")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    name = str(payload.get("name") or "attached-project")
    project_root = str(payload.get("project_root") or "")
    return build_profile_project_id(name, project_root)


def build_attachment_profile_name(payload: dict[str, object], profile: str | None = None) -> str:
    if profile and profile.strip():
        return sanitize_profile_name(profile)
    payload_profile = payload.get("profile")
    if isinstance(payload_profile, str) and payload_profile.strip():
        return sanitize_profile_name(payload_profile)
    explicit_name = payload.get("name")
    if isinstance(explicit_name, str) and explicit_name.strip():
        return sanitize_profile_name(explicit_name)
    return "default"


def component_id_for_path(
    path: Path | str | None,
    source_settings: dict[str, object] | None = None,
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
    project_root: Path | str | None = None,
) -> dict[str, object]:
    payload = {
        "source": "attachment",
        "attachment_path": str(attachment_path),
        "scan_roots": [normalize_path(path) for path in (scan_roots or [])],
        "design_roots": [normalize_path(path) for path in (design_roots or [])],
        "project_root": normalize_path(project_root) if project_root is not None else None,
    }
    return payload


def source_signature(payload: dict[str, object] | None = None) -> str:
    data = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


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


def normalize_attachment_json(payload: object) -> dict[str, object]:
    return normalize_attachment_payload(payload if isinstance(payload, dict) else {})


def load_attachment_config(path: Path = DEFAULT_ATTACHMENT_PATH, *, profile: str | None = None) -> dict[str, object] | None:
    config_path = path if path.is_absolute() else (ROOT / path).resolve()
    if not config_path.exists():
        return None
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    if profile:
        profiles = payload.get("profiles")
        if isinstance(profiles, list):
            for item in profiles:
                if isinstance(item, dict) and item.get("profile") == profile:
                    return item
    return payload


def save_attachment_config(path: Path = DEFAULT_ATTACHMENT_PATH, payload: dict[str, object] | None = None) -> Path:
    effective_path = path if path.is_absolute() else (ROOT / path).resolve()
    data = dict(payload or {})
    atomic_write_text(effective_path, json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return effective_path


def list_attachment_profiles(path: Path = DEFAULT_ATTACHMENT_PATH) -> list[dict[str, object]]:
    config = load_attachment_config(path)
    if not isinstance(config, dict):
        return []
    profiles = config.get("profiles")
    if not isinstance(profiles, list):
        return []
    result: list[dict[str, object]] = []
    for item in profiles:
        normalized = normalize_attachment_json(item)
        if normalized:
            result.append(normalized)
    return result
