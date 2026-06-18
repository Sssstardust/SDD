#!/usr/bin/env python3
"""
Small Gate 2 checking helpers.
"""

from __future__ import annotations

from typing import Any


def build_missing_req_error() -> str:
    return "No REQ-IDs found in 需求规格.md"


def summarize_req_coverage(coverage: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for req_id, files in coverage.items():
        if isinstance(files, list) and files:
            continue
        missing.append(str(req_id))
    return sorted(set(missing))

