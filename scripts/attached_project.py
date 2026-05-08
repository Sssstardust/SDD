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
DEFAULT_ATTACHMENTS_DIR = DEFAULT_ATTACHMENT_PATH.parent / "attachments"
DEFAULT_ATTACHMENT_REGISTRY_PATH = DEFAULT_ATTACHMENTS_DIR / "registry.json"
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

def _read_attachment_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return normalize_attachment_payload(payload) if isinstance(payload, dict) else None


def _implicit_legacy_profile(attachment_path: Path) -> dict[str, object] | None:
    effective_attachment_path = attachment_path if attachment_path.is_absolute() else (ROOT / attachment_path).resolve()
    payload = _read_attachment_json(effective_attachment_path)
    if payload is None:
        return None
    project_id = build_attachment_project_id(payload)
    profile_name = build_attachment_profile_name(payload)
    payload["project_id"] = project_id
    payload["profile"] = profile_name
    return {
        "profile": profile_name,
        "active": True,
        "project_id": project_id,
        "name": payload.get("name"),
        "project_root": payload.get("project_root"),
        "attachment_file": str(effective_attachment_path),
        "payload": payload,
    }


def load_attachment_registry(attachment_path: Path = DEFAULT_ATTACHMENT_PATH) -> dict[str, object] | None:
    path = attachment_registry_path_for(attachment_path)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def save_attachment_registry(payload: dict[str, object], attachment_path: Path = DEFAULT_ATTACHMENT_PATH) -> Path:
    path = attachment_registry_path_for(attachment_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def list_attachment_profiles(attachment_path: Path = DEFAULT_ATTACHMENT_PATH) -> list[dict[str, object]]:
    registry = load_attachment_registry(attachment_path)
    if not isinstance(registry, dict):
        implicit = _implicit_legacy_profile(attachment_path)
        if implicit is None:
            return []
        return [{key: value for key, value in implicit.items() if key != "payload"}]
    profiles = registry.get("profiles")
    active_profile = registry.get("active_profile")
    if not isinstance(profiles, dict):
        return []
    items: list[dict[str, object]] = []
    for profile_name, raw_meta in sorted(profiles.items()):
        if not isinstance(raw_meta, dict):
            continue
        item = dict(raw_meta)
        item["profile"] = profile_name
        item["active"] = profile_name == active_profile
        items.append(item)
    return items


def resolve_attachment_profile_path(
    attachment_path: Path = DEFAULT_ATTACHMENT_PATH,
    *,
    profile: str | None = None,
) -> Path | None:
    registry = load_attachment_registry(attachment_path)
    effective_attachment_path = attachment_path if attachment_path.is_absolute() else (ROOT / attachment_path).resolve()
    if isinstance(registry, dict):
        profiles = registry.get("profiles")
        if isinstance(profiles, dict):
            target_profile = sanitize_profile_name(profile) if profile else registry.get("active_profile")
            if isinstance(target_profile, str):
                raw_meta = profiles.get(target_profile)
                if isinstance(raw_meta, dict):
                    attachment_file = raw_meta.get("attachment_file")
                    if isinstance(attachment_file, str) and attachment_file:
                        return Path(attachment_file)
    implicit = _implicit_legacy_profile(effective_attachment_path)
    if implicit is not None:
        if profile:
            target_profile = sanitize_profile_name(profile)
            if implicit.get("profile") != target_profile:
                return None
        attachment_file = implicit.get("attachment_file")
        if isinstance(attachment_file, str) and attachment_file:
            return Path(attachment_file)
    return effective_attachment_path if effective_attachment_path.exists() and not profile else None


def set_active_attachment_profile(profile: str, attachment_path: Path = DEFAULT_ATTACHMENT_PATH) -> dict[str, object]:
    registry = load_attachment_registry(attachment_path)
    if not isinstance(registry, dict):
        implicit = _implicit_legacy_profile(attachment_path)
        normalized_profile = sanitize_profile_name(profile)
        if implicit is None or implicit.get("profile") != normalized_profile:
            raise ValueError("attachment profile registry does not exist")
        payload = implicit.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("attachment profile registry does not exist")
        save_attachment_config(payload, attachment_path, profile=normalized_profile, project_id=str(payload.get("project_id") or ""))
        registry = load_attachment_registry(attachment_path)
        if not isinstance(registry, dict):
            raise ValueError("failed to initialize attachment profile registry")
    normalized_profile = sanitize_profile_name(profile)
    profiles = registry.get("profiles")
    if not isinstance(profiles, dict) or normalized_profile not in profiles:
        raise ValueError(f"attachment profile not found: {normalized_profile}")
    registry["active_profile"] = normalized_profile
    save_attachment_registry(registry, attachment_path)
    payload = load_attachment_config(attachment_path, profile=normalized_profile)
    if isinstance(payload, dict):
        effective_attachment_path = attachment_path if attachment_path.is_absolute() else (ROOT / attachment_path).resolve()
        effective_attachment_path.parent.mkdir(parents=True, exist_ok=True)
        effective_attachment_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return registry


def save_attachment_config(
    payload: dict[str, object],
    attachment_path: Path = DEFAULT_ATTACHMENT_PATH,
    *,
    profile: str | None = None,
    project_id: str | None = None,
    set_active: bool = True,
) -> Path:
    effective_attachment_path = attachment_path if attachment_path.is_absolute() else (ROOT / attachment_path).resolve()
    effective_attachment_path.parent.mkdir(parents=True, exist_ok=True)

    normalized_payload = normalize_attachment_payload(payload)
    normalized_payload["project_id"] = project_id or build_attachment_project_id(normalized_payload)
    normalized_payload["profile"] = build_attachment_profile_name(normalized_payload, profile)

    profiles_dir = attachment_profiles_dir_for(effective_attachment_path)
    profiles_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profiles_dir / f"{normalized_payload['project_id']}.json"
    profile_path.write_text(json.dumps(normalized_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    registry = load_attachment_registry(effective_attachment_path) or {"version": 1, "active_profile": None, "profiles": {}}
    profiles = registry.get("profiles")
    if not isinstance(profiles, dict):
        profiles = {}
        registry["profiles"] = profiles

    profile_name = str(normalized_payload["profile"])
    profiles[profile_name] = {
        "project_id": normalized_payload["project_id"],
        "name": normalized_payload.get("name"),
        "project_root": normalized_payload.get("project_root"),
        "attachment_file": str(profile_path),
    }
    if set_active or not registry.get("active_profile"):
        registry["active_profile"] = profile_name
        effective_attachment_path.write_text(json.dumps(normalized_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    elif not effective_attachment_path.exists():
        effective_attachment_path.write_text(json.dumps(normalized_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    save_attachment_registry(registry, effective_attachment_path)
    return effective_attachment_path


def remove_attachment_profile(
    attachment_path: Path = DEFAULT_ATTACHMENT_PATH,
    *,
    profile: str | None = None,
    clear_all: bool = False,
) -> None:
    effective_attachment_path = attachment_path if attachment_path.is_absolute() else (ROOT / attachment_path).resolve()
    if clear_all:
        if effective_attachment_path.exists():
            effective_attachment_path.unlink()
        registry_path = attachment_registry_path_for(effective_attachment_path)
        if registry_path.exists():
            registry_path.unlink()
        profiles_dir = attachment_profiles_dir_for(effective_attachment_path)
        if profiles_dir.exists():
            for child in profiles_dir.glob("*.json"):
                child.unlink()
            try:
                profiles_dir.rmdir()
            except OSError:
                pass
        attachments_dir = attachments_dir_for(effective_attachment_path)
        if attachments_dir.exists():
            try:
                attachments_dir.rmdir()
            except OSError:
                pass
        return

    registry = load_attachment_registry(effective_attachment_path)
    if not isinstance(registry, dict):
        if effective_attachment_path.exists():
            effective_attachment_path.unlink()
        return

    profiles = registry.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        if effective_attachment_path.exists():
            effective_attachment_path.unlink()
        return

    target_profile = sanitize_profile_name(profile) if profile else registry.get("active_profile")
    if not isinstance(target_profile, str) or target_profile not in profiles:
        raise ValueError(f"attachment profile not found: {target_profile}")

    raw_meta = profiles.pop(target_profile)
    if isinstance(raw_meta, dict):
        attachment_file = raw_meta.get("attachment_file")
        if isinstance(attachment_file, str) and attachment_file:
            path = Path(attachment_file)
            if path.exists():
                path.unlink()

    if not profiles:
        remove_attachment_profile(effective_attachment_path, clear_all=True)
        return

    if registry.get("active_profile") == target_profile:
        registry["active_profile"] = sorted(profiles.keys())[0]
        replacement = load_attachment_config(effective_attachment_path, profile=str(registry["active_profile"]))
        if isinstance(replacement, dict):
            effective_attachment_path.write_text(json.dumps(replacement, ensure_ascii=False, indent=2), encoding="utf-8")

    save_attachment_registry(registry, effective_attachment_path)


def load_attachment_config(
    attachment_path: Path = DEFAULT_ATTACHMENT_PATH,
    *,
    profile: str | None = None,
) -> dict[str, object] | None:
    effective_attachment_path = attachment_path if attachment_path.is_absolute() else (ROOT / attachment_path).resolve()
    profile_path = resolve_attachment_profile_path(effective_attachment_path, profile=profile)
    if profile_path is not None:
        payload = _read_attachment_json(profile_path)
        if payload is not None:
            if not isinstance(payload.get("project_id"), str) or not str(payload.get("project_id")).strip():
                payload["project_id"] = build_attachment_project_id(payload)
            if not isinstance(payload.get("profile"), str) or not str(payload.get("profile")).strip():
                payload["profile"] = build_attachment_profile_name(payload, profile)
            return payload
    return None


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
    profile: str | None = None,
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

    attachment = load_attachment_config(attachment_path, profile=profile)
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
