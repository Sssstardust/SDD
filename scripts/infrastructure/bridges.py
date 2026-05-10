#!/usr/bin/env python3
"""
Infrastructure-layer bridge exports.
"""

from __future__ import annotations

from .concurrency import atomic_write_text, feature_lock, path_lock
from .json_io import read_json, write_json
from .ops_log import append_project_op, read_latest_op, read_recent_ops
from .sdd_yaml import extract_yaml_blocks, get_list, get_scalar, load_merged_yaml_mapping

__all__ = [
    "atomic_write_text",
    "feature_lock",
    "path_lock",
    "read_json",
    "write_json",
    "append_project_op",
    "read_latest_op",
    "read_recent_ops",
    "extract_yaml_blocks",
    "get_list",
    "get_scalar",
    "load_merged_yaml_mapping",
]
