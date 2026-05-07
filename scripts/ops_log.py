#!/usr/bin/env python3
"""
ops_log.py

记录项目级控制台相关操作日志。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OPS_DIR = ROOT / ".spec" / "ops"
OPS_LOG = OPS_DIR / "project-ops.jsonl"


def append_project_op(op_type: str, payload: dict) -> Path:
    OPS_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "at": datetime.now(timezone.utc).isoformat(),
        "op_type": op_type,
        "payload": payload,
    }
    with OPS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return OPS_LOG


def read_recent_ops(limit: int = 10) -> list[dict]:
    if not OPS_LOG.exists():
        return []
    lines = OPS_LOG.read_text(encoding="utf-8").splitlines()
    entries = [json.loads(line) for line in lines if line.strip()]
    return entries[-limit:]


def read_latest_op(op_types: list[str]) -> dict | None:
    if not OPS_LOG.exists():
        return None
    lines = OPS_LOG.read_text(encoding="utf-8").splitlines()
    for line in reversed(lines):
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("op_type") in op_types:
            return entry
    return None
