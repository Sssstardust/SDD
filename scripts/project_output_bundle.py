#!/usr/bin/env python3
"""
Shared helpers for project-level output commands.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from attached_project import DEFAULT_ATTACHMENT_PATH
from json_io import write_json
from project_artifact_paths import get_active_project_artifacts_dir
from project_state_bundle import collect_project_state_bundle


def resolve_output_dir(
    *,
    output_dir: str | None,
    attachment_path: Path = DEFAULT_ATTACHMENT_PATH,
    profile: str | None = None,
) -> Path:
    target = (
        Path(output_dir)
        if output_dir
        else get_active_project_artifacts_dir(attachment_path=attachment_path, profile=profile, create=True)
    )
    target.mkdir(parents=True, exist_ok=True)
    return target


def build_project_level_payload(
    *,
    attachment_path: Path = DEFAULT_ATTACHMENT_PATH,
    profile: str | None = None,
    include_recent_ops: bool = False,
) -> dict[str, object]:
    payload = collect_project_state_bundle(
        attachment_path=attachment_path,
        profile=profile,
        include_recent_ops=include_recent_ops,
    )
    states = payload["features"]
    payload["stage_counts"] = dict(Counter(str(state.get("current_stage", "unknown")) for state in states))
    payload["strict_recommended_count"] = sum(1 for state in states if state.get("strict_recommended"))
    payload["strict_next_step_count"] = sum(1 for state in states if state.get("strict_next_step"))
    return payload


def write_project_json(output_dir: Path, file_name: str, payload: dict[str, object]) -> Path:
    json_path = output_dir / file_name
    write_json(json_path, payload)
    return json_path
