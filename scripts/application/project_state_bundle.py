#!/usr/bin/env python3
"""
Shared project-level state collection helpers.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from domain.attached_project import DEFAULT_ATTACHMENT_PATH, build_workspace_payload
from application.flow_state import inspect_feature_state
from infrastructure.ops_log import read_latest_op, read_recent_ops
from infrastructure.project_artifact_paths import describe_active_project_artifacts
from infrastructure.versioning import iter_feature_dirs


def collect_project_state_bundle(
    *,
    attachment_path: Path = DEFAULT_ATTACHMENT_PATH,
    profile: str | None = None,
    include_recent_ops: bool = False,
) -> dict[str, object]:
    states = [inspect_feature_state(feature_dir) for feature_dir in iter_feature_dirs(attachment_path=attachment_path, profile=profile)]
    project_context = describe_active_project_artifacts(attachment_path=attachment_path, profile=profile, create=True)
    workspace = build_workspace_payload(attachment_path)
    payload: dict[str, object] = {
        "project": project_context,
        "workspace": workspace,
        "feature_count": len(states),
        "state_source_policy": "prefer_persisted",
        "state_source_counts": dict(Counter(str(state.get("state_source", "unknown")) for state in states)),
        "features": states,
        "latest_execution": read_latest_op(["continue-project-flow", "project-cycle"]),
    }
    if include_recent_ops:
        payload["recent_ops"] = read_recent_ops(10)
    return payload

