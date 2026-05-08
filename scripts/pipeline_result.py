#!/usr/bin/env python3
"""
Helpers for emitting structured pipeline command results.
"""

from __future__ import annotations

import json
from typing import Any


def build_result(
    *,
    status: str,
    message: str,
    data: dict[str, Any] | None = None,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
    artifacts: dict[str, Any] | None = None,
    next_actions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "message": message,
        "data": data or {},
        "errors": errors or [],
        "warnings": warnings or [],
        "artifacts": artifacts or {},
        "next_actions": next_actions or [],
    }


def emit_result(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=True, indent=2))
