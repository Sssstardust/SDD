#!/usr/bin/env python3
"""
Helpers for lightweight gate cache state.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .baseline_paths import get_active_baseline_dir
from .versioning import detect_latest_design_path, reports_dir_for_design, resolve_feature_dir
from design_evidence import hash_file


DESIGN_GATE_NAMES = ("gate1", "gate2", "gate3")
IMPLEMENTATION_GATE_NAMES = ("gate4", "gate5")


def _stable_hash_text(path: Path) -> str:
    value = hash_file(path)
    return str(value) if value is not None else "missing"


def _base_design_gate_payload_parts(feature_dir: Path) -> list[str]:
    feature_dir = resolve_feature_dir(feature_dir)
    feature_brief = feature_dir / "feature-brief.md"
    design_path = detect_latest_design_path(feature_dir)
    return [
        str(feature_dir),
        _stable_hash_text(feature_brief),
        _stable_hash_text(design_path),
        design_path.name,
    ]


def design_gate_cache_input_hash(feature_dir: Path) -> str:
    payload_parts = _base_design_gate_payload_parts(resolve_feature_dir(feature_dir))
    return hashlib.sha256("::".join(payload_parts).encode("utf-8")).hexdigest()


def design_gate_input_hash(feature_dir: Path, gate_name: str) -> str:
    feature_dir = resolve_feature_dir(feature_dir)
    payload_parts = _base_design_gate_payload_parts(feature_dir)
    baseline_dir = get_active_baseline_dir(create=True, migrate_legacy=True)
    if gate_name in {"gate2", "gate3"}:
        payload_parts.extend(
            [
                _stable_hash_text(baseline_dir / "module-map.json"),
                _stable_hash_text(baseline_dir / "schema-context.json"),
            ]
        )
    return hashlib.sha256("::".join(payload_parts).encode("utf-8")).hexdigest()


def implementation_gate_input_hash(feature_dir: Path, gate_name: str) -> str:
    feature_dir = resolve_feature_dir(feature_dir)
    payload_parts = _base_design_gate_payload_parts(feature_dir)
    baseline_dir = get_active_baseline_dir(create=True, migrate_legacy=True)
    payload_parts.extend(
        [
            _stable_hash_text(baseline_dir / "module-map.json"),
            _stable_hash_text(baseline_dir / "schema-context.json"),
        ]
    )
    reports_dir = reports_dir_for_design(feature_dir, detect_latest_design_path(feature_dir))
    payload_parts.append(_stable_hash_text(reports_dir / "gate4-skeleton.json"))
    if gate_name == "gate5":
        payload_parts.append(_stable_hash_text(reports_dir / "gate-report.json"))
    return hashlib.sha256("::".join(payload_parts).encode("utf-8")).hexdigest()


def build_gate_cache_entry(
    *,
    status: str,
    input_hash: str,
    report_path: str,
    completed_at: str | None = None,
) -> dict[str, object]:
    return {
        "status": status,
        "input_hash": input_hash,
        "report_path": report_path,
        "completed_at": completed_at,
    }


def read_design_gate_cache_from_state(state: object) -> dict[str, dict[str, object]]:
    if not isinstance(state, dict):
        return {}
    raw_cache = state.get("gate_cache")
    if not isinstance(raw_cache, dict):
        return {}
    normalized: dict[str, dict[str, object]] = {}
    for gate_name in (*DESIGN_GATE_NAMES, *IMPLEMENTATION_GATE_NAMES):
        raw_entry = raw_cache.get(gate_name)
        if isinstance(raw_entry, dict):
            normalized[gate_name] = dict(raw_entry)
    return normalized


def update_design_gate_cache(
    existing: dict[str, dict[str, object]],
    *,
    gate_name: str,
    status: str,
    input_hash: str,
    report_path: str,
    completed_at: str | None = None,
) -> dict[str, dict[str, object]]:
    updated = dict(existing)
    updated[gate_name] = build_gate_cache_entry(
        status=status,
        input_hash=input_hash,
        report_path=report_path,
        completed_at=completed_at,
    )
    return updated


def should_skip_design_gate(
    gate_cache: dict[str, dict[str, object]],
    *,
    gate_name: str,
    input_hash: str,
) -> bool:
    entry = gate_cache.get(gate_name)
    if not isinstance(entry, dict):
        return False
    return entry.get("status") == "PASS" and entry.get("input_hash") == input_hash


def gate_report_path_for(feature_dir: Path, gate_name: str) -> Path:
    design_path = detect_latest_design_path(feature_dir)
    reports_dir = reports_dir_for_design(feature_dir, design_path)
    if gate_name == "gate1":
        return reports_dir / "gate1-report.json"
    return reports_dir / "gate-report.json"


def load_gate_result_from_report(feature_dir: Path, gate_name: str) -> tuple[str | None, str | None]:
    report_path = gate_report_path_for(feature_dir, gate_name)
    if not report_path.exists():
        return None, None
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, str(report_path)
    if gate_name == "gate1":
        result = payload.get("result") if isinstance(payload, dict) else None
        return str(result) if isinstance(result, str) else None, str(report_path)
    gate_payload = payload.get(gate_name) if isinstance(payload, dict) else None
    if not isinstance(gate_payload, dict):
        return None, str(report_path)
    result = gate_payload.get("result")
    return str(result) if isinstance(result, str) else None, str(report_path)


def current_timestamp_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
