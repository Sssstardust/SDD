#!/usr/bin/env python3
"""
Shared JSON read/write helpers with UTF-8 BOM tolerance.
"""

from __future__ import annotations

import json
from pathlib import Path

from .concurrency import atomic_write_text


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: object) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

