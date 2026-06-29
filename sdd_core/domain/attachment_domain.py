#!/usr/bin/env python3
"""
Domain entities and core helpers for target project attachments (FIX-017).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from sdd_core.domain.language_profiles import get_language_profile

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ATTACHMENT_PATH = ROOT / ".spec" / "attached-project.json"
DEFAULT_ATTACHMENTS_DIR = DEFAULT_ATTACHMENT_PATH.parent / "attachments"
DEFAULT_ATTACHMENT_REGISTRY_PATH = DEFAULT_ATTACHMENTS_DIR / "registry.json"
DEFAULT_WORKSPACE_PATH = DEFAULT_ATTACHMENT_PATH.parent / "workspace.json"

COMPONENT_ROOT_FIELDS = {"scan_roots", "design_roots", "schema_roots"}
COMPONENT_RESERVED_FIELDS = {"component_id", "name", "project_root", "language", *COMPONENT_ROOT_FIELDS}
ATTACHMENT_ROOT_FIELDS = {"scan_roots", "design_roots", "schema_roots"}
ATTACHMENT_RESERVED_FIELDS = {"name", "project_root", "components", *ATTACHMENT_ROOT_FIELDS}
ATTACHMENT_STATE_FIELDS = {"profiles", "active_profile", "active_project_id"}
RISK_TIERS_REQUIRING_VERIFICATION_COMMANDS = {"high", "critical"}


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


def default_scan_roots(project_root: Path, language: str | None = None) -> list[Path]:
    profile = get_language_profile(language)
    return [project_root / Path(rel) for rel in profile.scan_roots]


def default_schema_roots(project_root: Path, language: str | None = None) -> list[Path]:
    profile = get_language_profile(language)
    return [project_root / Path(rel) for rel in profile.schema_roots]


def is_fixture_attachment(path: Path | str) -> bool:
    lowered = str(path).replace("/", "\\").lower()
    return "\\examples\\fixtures\\" in lowered or "attached-sample-project" in lowered


def build_attachment_project_id(payload: dict[str, Any]) -> str:
    explicit = payload.get("project_id")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    name = str(payload.get("name") or "attached-project")
    project_root = str(payload.get("project_root") or "")
    return build_profile_project_id(name, project_root)


def build_attachment_profile_name(payload: dict[str, Any], profile: str | None = None) -> str:
    if profile and profile.strip():
        return sanitize_profile_name(profile)
    payload_profile = payload.get("profile")
    if isinstance(payload_profile, str) and payload_profile.strip():
        return sanitize_profile_name(payload_profile)
    explicit_name = payload.get("name")
    if isinstance(explicit_name, str) and explicit_name.strip():
        return sanitize_profile_name(explicit_name)
    return "default"


def validate_components_for_risk_tier(
    components: list[dict[str, Any]] | None,
    risk_tier: str,
) -> list[str]:
    warnings: list[str] = []
    if risk_tier not in RISK_TIERS_REQUIRING_VERIFICATION_COMMANDS:
        return warnings
    if not isinstance(components, list):
        return warnings
    for component in components:
        if not isinstance(component, dict):
            continue
        component_id = str(component.get("component_id") or component.get("name") or "component").strip()
        cmds = component.get("verification_commands") or component.get("test_commands")
        if not isinstance(cmds, list) or not cmds:
            warnings.append(
                f"[ONBOARD WARN] 组件 '{component_id}' 缺少 verification_commands。"
                f" 高风险功能（risk_tier={risk_tier}）的 gate5 attached_execution 将 FAIL。"
            )
    return warnings
