#!/usr/bin/env python3
"""
Application-layer helpers for writing gate cache state.
"""

from __future__ import annotations

import json
from pathlib import Path

from sdd_core.infrastructure.concurrency import atomic_write_text, feature_lock
from sdd_core.infrastructure.gate_cache import (
    DESIGN_GATE_NAMES,
    IMPLEMENTATION_GATE_NAMES,
    current_timestamp_iso,
    design_gate_input_hash,
    implementation_gate_input_hash,
    load_gate_result_from_report,
    read_design_gate_cache_from_state,
    update_design_gate_cache,
)
from sdd_core.infrastructure.json_io import read_json
from sdd_core.infrastructure.feature_artifact_paths import project_state_path, resolve_project_state_path
from sdd_core.infrastructure.versioning import resolve_feature_dir


def write_gate_cache_entry(feature_dir: str | Path, gate_name: str) -> None:
    if gate_name not in (*DESIGN_GATE_NAMES, *IMPLEMENTATION_GATE_NAMES):
        return
    feature_path = resolve_feature_dir(str(feature_dir))
    existing_project_state_file = resolve_project_state_path(feature_path)
    project_state_file = project_state_path(feature_path, create_parent=True)
    existing_state = read_json(existing_project_state_file) if existing_project_state_file.exists() else {}
    existing_cache = read_design_gate_cache_from_state(existing_state)
    result, report_path = load_gate_result_from_report(feature_path, gate_name)
    if not result or not report_path:
        return
    input_hash = (
        design_gate_input_hash(feature_path, gate_name)
        if gate_name in DESIGN_GATE_NAMES
        else implementation_gate_input_hash(feature_path, gate_name)
    )
    updated_cache = update_design_gate_cache(
        existing_cache,
        gate_name=gate_name,
        status=result,
        input_hash=input_hash,
        report_path=report_path,
        completed_at=current_timestamp_iso(),
    )
    if not isinstance(existing_state, dict):
        existing_state = {}
    existing_state["gate_cache"] = updated_cache
    with feature_lock(feature_path, phase=f"gate-cache:{gate_name}"):
        atomic_write_text(
            project_state_file,
            json.dumps(existing_state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
