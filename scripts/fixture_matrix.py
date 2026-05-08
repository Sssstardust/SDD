#!/usr/bin/env python3
"""
Helpers for bundled example feature fixtures.
"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path, PurePosixPath

from concurrency import atomic_write_text


ROOT = Path(__file__).resolve().parent.parent
FIXTURE_ROOT = ROOT / "examples" / "fixtures"
DEFAULT_WORKSPACE_ROOT = ROOT / ".tmp_test_workspace" / "fixture-matrix"
MANIFEST_NAME = "fixture-meta.json"


def fixture_relative_prefix(source_dir: Path) -> str:
    try:
        return source_dir.relative_to(ROOT).as_posix()
    except ValueError:
        return source_dir.resolve().as_posix()


def rewrite_fixture_string(value: str, source_dir: Path, target_dir: Path) -> str:
    source_abs = source_dir.resolve().as_posix()
    target_abs = target_dir.resolve().as_posix()
    source_rel = fixture_relative_prefix(source_dir)
    normalized = value.replace("\\", "/")
    if source_abs in normalized:
        return value.replace(str(source_dir.resolve()), str(target_dir.resolve()))
    if normalized.startswith(source_rel):
        suffix = normalized[len(source_rel):].lstrip("/")
        return str(target_dir / PurePosixPath(suffix))
    return value


def rewrite_fixture_payload(value: object, source_dir: Path, target_dir: Path) -> object:
    if isinstance(value, dict):
        return {key: rewrite_fixture_payload(item, source_dir, target_dir) for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite_fixture_payload(item, source_dir, target_dir) for item in value]
    if isinstance(value, str):
        return rewrite_fixture_string(value, source_dir, target_dir)
    return value


def rewrite_fixture_reports(source_dir: Path, target_dir: Path) -> None:
    reports_dir = target_dir / "reports"
    if not reports_dir.exists():
        return
    for report_path in reports_dir.rglob("*.json"):
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        rewritten = rewrite_fixture_payload(payload, source_dir, target_dir)
        atomic_write_text(
            report_path,
            json.dumps(rewritten, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def prepare_feature_fixture(source_dir: Path, workspace_root: Path) -> Path:
    workspace_root.mkdir(parents=True, exist_ok=True)
    target_dir = workspace_root / source_dir.name
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
    shutil.copytree(source_dir, target_dir)
    rewrite_fixture_reports(source_dir, target_dir)
    return target_dir


def build_workspace_root(*, name: str) -> Path:
    DEFAULT_WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    return DEFAULT_WORKSPACE_ROOT / f"{name}-{uuid.uuid4().hex}"


def load_fixture_manifest(fixture_dir: Path) -> dict[str, object] | None:
    manifest_path = fixture_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return None
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def discover_feature_fixtures() -> list[dict[str, object]]:
    fixtures: list[dict[str, object]] = []
    for fixture_dir in sorted(path for path in FIXTURE_ROOT.iterdir() if path.is_dir()):
        manifest = load_fixture_manifest(fixture_dir)
        if not manifest:
            continue
        fixture = dict(manifest)
        fixture["path"] = str(fixture_dir)
        fixture["name"] = str(manifest.get("name") or fixture_dir.name)
        fixtures.append(fixture)
    return fixtures
