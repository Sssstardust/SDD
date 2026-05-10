#!/usr/bin/env python3
"""
Small Gate 2 checking helpers.
"""

from __future__ import annotations


def build_missing_req_error() -> str:
    return "No REQ-IDs found in feature-brief.md"


def summarize_req_coverage(coverage: dict[str, object]) -> list[str]:
    missing: list[str] = []
    for req_id, files in coverage.items():
        if isinstance(files, list) and files:
            continue
        missing.append(str(req_id))
    return sorted(set(missing))

