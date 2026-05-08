#!/usr/bin/env python3
"""
versioning.py

集中处理 design-v{N}.md 与 reports/v{N}/ 的版本解析逻辑。
"""

from __future__ import annotations

import re
from pathlib import Path

from attached_project import DEFAULT_ATTACHMENT_PATH, load_attachment_config

DESIGN_PATTERN = re.compile(r"^design-v(\d+)\.md$")
ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = ROOT / "specs"


def _design_version_number(path: Path) -> int:
    match = DESIGN_PATTERN.match(path.name)
    return int(match.group(1)) if match else -1


def list_design_files(feature_dir: Path) -> list[Path]:
    return sorted(
        (path for path in feature_dir.glob("design-v*.md") if DESIGN_PATTERN.match(path.name)),
        key=_design_version_number,
    )


def detect_latest_design_path(feature_dir: Path) -> Path:
    design_files = list_design_files(feature_dir)
    return design_files[-1] if design_files else feature_dir / "design-v1.md"


def resolve_design_path(feature_dir: Path, design_version: str | None = None) -> Path:
    if not design_version:
        return detect_latest_design_path(feature_dir)
    value = design_version.strip()
    if not value:
        return detect_latest_design_path(feature_dir)
    if DESIGN_PATTERN.match(value):
        return feature_dir / value
    version_match = re.match(r"^v(\d+)$", value, re.IGNORECASE)
    if version_match:
        return feature_dir / f"design-v{version_match.group(1)}.md"
    number_match = re.match(r"^(\d+)$", value)
    if number_match:
        return feature_dir / f"design-v{number_match.group(1)}.md"
    return feature_dir / value


def detect_next_design_path(feature_dir: Path) -> Path:
    latest = detect_latest_design_path(feature_dir)
    if latest.exists():
        next_version = design_version_number(latest) + 1
        return feature_dir / f"design-v{next_version}.md"
    return latest


def design_version_number(design_path_or_name: Path | str) -> int:
    name = design_path_or_name.name if isinstance(design_path_or_name, Path) else design_path_or_name
    match = DESIGN_PATTERN.match(name)
    return int(match.group(1)) if match else 1


def reports_dir_for_design(feature_dir: Path, design_path_or_name: Path | str) -> Path:
    return feature_dir / "reports" / f"v{design_version_number(design_path_or_name)}"


def get_design_roots(attachment_path: Path = DEFAULT_ATTACHMENT_PATH, profile: str | None = None) -> list[Path]:
    attachment = load_attachment_config(attachment_path, profile=profile)
    if isinstance(attachment, dict):
        design_roots = attachment.get("design_roots")
        if isinstance(design_roots, list):
            roots = [Path(item).resolve() for item in design_roots if isinstance(item, str)]
            if roots:
                return roots
    return [SPECS_DIR.resolve()]


def get_primary_design_root(attachment_path: Path = DEFAULT_ATTACHMENT_PATH, profile: str | None = None) -> Path:
    return get_design_roots(attachment_path, profile=profile)[0]


def iter_feature_dirs(attachment_path: Path = DEFAULT_ATTACHMENT_PATH, profile: str | None = None) -> list[Path]:
    feature_dirs: list[Path] = []
    seen: set[Path] = set()
    for design_root in get_design_roots(attachment_path, profile=profile):
        if not design_root.exists():
            continue
        for path in sorted(design_root.iterdir()):
            resolved = path.resolve()
            if not resolved.is_dir():
                continue
            if resolved.name.startswith(".") or resolved.name.startswith("_"):
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            feature_dirs.append(resolved)
    return feature_dirs


def resolve_feature_dir(
    feature_dir_or_path: Path | str,
    attachment_path: Path = DEFAULT_ATTACHMENT_PATH,
    profile: str | None = None,
) -> Path:
    path = feature_dir_or_path if isinstance(feature_dir_or_path, Path) else Path(feature_dir_or_path)
    if path.is_absolute():
        return path

    candidate_roots = get_design_roots(attachment_path, profile=profile)
    relative_path = Path(*path.parts[1:]) if path.parts and path.parts[0].lower() == "specs" else path

    for design_root in candidate_roots:
        candidate = (design_root / relative_path).resolve()
        if candidate.exists():
            return candidate

    return (get_primary_design_root(attachment_path, profile=profile) / relative_path).resolve()
