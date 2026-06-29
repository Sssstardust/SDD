#!/usr/bin/env python3
"""
IO and persistence services for target project attachments (FIX-017).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sdd_core.domain.repositories import AttachmentConfigRepository
from sdd_core.domain.attachment_domain import (
    ROOT,
    DEFAULT_ATTACHMENT_PATH,
    ATTACHMENT_STATE_FIELDS,
)
from sdd_core.domain.attachment_service import (
    normalize_attachment_json,
    build_attachment_project_id,
    build_attachment_profile_name,
)

logger = logging.getLogger(__name__)

_config_repo: AttachmentConfigRepository | None = None


def get_config_repository() -> AttachmentConfigRepository:
    global _config_repo
    if _config_repo is None:
        from sdd_core.infrastructure.attachment_config_repo import FileAttachmentConfigRepository
        _config_repo = FileAttachmentConfigRepository()
    return _config_repo


def set_config_repository(repo: AttachmentConfigRepository) -> None:
    global _config_repo
    _config_repo = repo


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


def write_attachment_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    get_config_repository().save(path, payload)
    return path


def build_workspace_payload(attachment_path: Path = DEFAULT_ATTACHMENT_PATH) -> dict[str, Any]:
    profiles = list_attachment_profiles(attachment_path)
    active = next((item for item in profiles if item.get("active") is True), None)
    if active is None and profiles:
        active = profiles[0]
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


def load_attachment_config(
    path: Path = DEFAULT_ATTACHMENT_PATH,
    *,
    profile: str | None = None,
) -> dict[str, Any] | None:
    config_path = path if path.is_absolute() else (ROOT / path).resolve()
    payload = get_config_repository().load(config_path)
    if payload is None:
        return None
    if not isinstance(payload, dict):
        return None
    if profile:
        profiles = payload.get("profiles")
        if isinstance(profiles, list):
            for item in profiles:
                if isinstance(item, dict) and item.get("profile") == profile:
                    return item
        if payload.get("profile") == profile:
            return payload
    return payload


def save_attachment_config(
    payload_or_path: dict[str, Any] | Path | None = None,
    path: Path = DEFAULT_ATTACHMENT_PATH,
    *,
    payload: dict[str, Any] | None = None,
    profile: str | None = None,
    project_id: str | None = None,
    set_active: bool = True,
) -> Path:
    if isinstance(payload_or_path, dict) and payload is None:
        data = dict(payload_or_path)
        effective_path = path if path.is_absolute() else (ROOT / path).resolve()
    else:
        effective_path = payload_or_path if isinstance(payload_or_path, Path) else (path if path.is_absolute() else (ROOT / path).resolve())
        data = dict(payload or {})
    if profile is not None:
        data["profile"] = profile
    if project_id is not None:
        data["project_id"] = project_id

    existing_payload = load_attachment_config(effective_path)
    existing_profiles = _attachment_profile_entries(existing_payload)
    entry_payload = {key: value for key, value in data.items() if key not in ATTACHMENT_STATE_FIELDS}
    entry = normalize_attachment_json(entry_payload)
    entry["profile"] = build_attachment_profile_name(entry, profile)
    if project_id is not None:
        entry["project_id"] = project_id
    elif not isinstance(entry.get("project_id"), str) or not entry.get("project_id"):
        entry["project_id"] = build_attachment_project_id(entry)

    profiles = [item for item in existing_profiles if item.get("profile") != entry["profile"]]
    profiles.append(entry)

    active_profile = next((item.get("profile") for item in profiles if item.get("active") is True), None)
    if set_active or active_profile is None:
        active_profile = str(entry["profile"])
    for item in profiles:
        item["active"] = item.get("profile") == active_profile

    active_entry = next((item for item in profiles if item.get("active") is True), entry)
    output = dict(active_entry)
    output["profiles"] = profiles
    output["active_profile"] = active_entry.get("profile")
    output["active_project_id"] = active_entry.get("project_id")

    write_attachment_json(effective_path, output)
    return effective_path


def load_attachment_seed(path: Path) -> dict[str, Any]:
    payload = get_config_repository().load(path)
    return payload if isinstance(payload, dict) else {}


def remove_attachment_profile(
    path: Path = DEFAULT_ATTACHMENT_PATH,
    *,
    profile: str | None = None,
    clear_all: bool = False,
) -> None:
    config_path = path if path.is_absolute() else (ROOT / path).resolve()
    if not config_path.exists():
        return
    if clear_all:
        config_path.unlink(missing_ok=True)
        return
    payload = load_attachment_config(config_path)
    if not isinstance(payload, dict):
        return
    profiles = _attachment_profile_entries(payload)
    if not profiles:
        return
    if profile is None:
        return
    remaining = [item for item in profiles if item.get("profile") != profile]
    if len(remaining) == len(profiles):
        return
    if not remaining:
        config_path.unlink(missing_ok=True)
        return

    active_profile = next((item.get("profile") for item in remaining if item.get("active") is True), None)
    if active_profile is None:
        active_profile = str(remaining[0].get("profile") or "")
    for item in remaining:
        item["active"] = item.get("profile") == active_profile

    active_entry = next((item for item in remaining if item.get("active") is True), remaining[0])
    output = dict(active_entry)
    output["profiles"] = remaining
    output["active_profile"] = active_entry.get("profile")
    output["active_project_id"] = active_entry.get("project_id")
    save_attachment_config(payload_or_path=config_path, payload=output)


def set_active_attachment_profile(profile: str, path: Path = DEFAULT_ATTACHMENT_PATH) -> None:
    config_path = path if path.is_absolute() else (ROOT / path).resolve()
    payload = load_attachment_config(config_path)
    if not isinstance(payload, dict):
        raise ValueError("no attached project is configured")
    profiles = _attachment_profile_entries(payload)
    if not profiles:
        raise ValueError(f"attachment profile not found: {profile}")
    matched = False
    for item in profiles:
        if isinstance(item, dict):
            item["active"] = item.get("profile") == profile
            matched = matched or item["active"] is True
    if not matched:
        raise ValueError(f"attachment profile not found: {profile}")
    active_entry = next((item for item in profiles if item.get("active") is True), profiles[0])
    output = dict(active_entry)
    output["profiles"] = profiles
    output["active_profile"] = active_entry.get("profile")
    output["active_project_id"] = active_entry.get("project_id")
    save_attachment_config(payload_or_path=config_path, payload=output)


def list_attachment_profiles(path: Path = DEFAULT_ATTACHMENT_PATH) -> list[dict[str, Any]]:
    config = load_attachment_config(path)
    return _attachment_profile_entries(config)


def _attachment_profile_entries(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    profiles = payload.get("profiles")
    if isinstance(profiles, list) and profiles:
        result: list[dict[str, Any]] = []
        for item in profiles:
            if not isinstance(item, dict):
                continue
            normalized = normalize_attachment_json({k: v for k, v in item.items() if k not in ATTACHMENT_STATE_FIELDS})
            if not normalized:
                continue
            if isinstance(item.get("active"), bool):
                normalized["active"] = bool(item.get("active"))
            result.append(normalized)
        return result

    if payload.get("profile") or payload.get("name"):
        normalized = normalize_attachment_json({k: v for k, v in payload.items() if k not in ATTACHMENT_STATE_FIELDS})
        if not normalized:
            return []
        if isinstance(payload.get("active"), bool):
            normalized["active"] = bool(payload.get("active"))
        else:
            normalized["active"] = True
        return [normalized]

    return []
