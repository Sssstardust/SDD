#!/usr/bin/env python3
"""
Helpers for versioned Design Pack snapshots and evidence hashes.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


def design_pack_snapshot_dir(reports_dir: Path) -> Path:
    return reports_dir / "design-pack.snapshot"


def freeze_design_pack(feature_dir: Path, reports_dir: Path) -> Path | None:
    source_dir = feature_dir / "design-pack"
    if not source_dir.exists():
        return None

    snapshot_dir = design_pack_snapshot_dir(reports_dir)
    if snapshot_dir.exists():
        shutil.rmtree(snapshot_dir)
    shutil.copytree(source_dir, snapshot_dir)
    return snapshot_dir


def resolve_design_pack_dir(feature_dir: Path, reports_dir: Path) -> Path:
    snapshot_dir = design_pack_snapshot_dir(reports_dir)
    if snapshot_dir.exists():
        return snapshot_dir
    return feature_dir / "design-pack"


def hash_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_tree(path: Path) -> str | None:
    if not path.exists():
        return None
    if path.is_file():
        return hash_file(path)

    digest = hashlib.sha256()
    files = sorted(item for item in path.rglob("*") if item.is_file())
    if not files:
        return hashlib.sha256(b"").hexdigest()

    for item in files:
        relative = item.relative_to(path).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        file_hash = hash_file(item) or ""
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def read_json_dict(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def evidence_level_for_schema_context(path: Path) -> str:
    payload = read_json_dict(path)
    source = str(payload.get("source") or "").lower()
    if source in {"polyquery", "database", "information_schema", "metadata"}:
        return "L1"
    if source in {"local-fallback", "local", "snapshot"}:
        return "L2"
    return "L2" if path.exists() else "L3"
