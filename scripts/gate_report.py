#!/usr/bin/env python3
"""
gate_report.py

维护 reports/v{N}/gate-report.json。
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path


def write_gate_section(
    reports_dir: Path,
    *,
    gate_name: str,
    feature_name: str,
    design_version: str,
    payload: dict,
) -> Path:
    reports_dir = reports_dir.resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = (reports_dir / "gate-report.json").resolve()

    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
    else:
        report = {
            "feature_name": feature_name,
            "design_version": design_version,
            "updated_at": None,
        }

    report["feature_name"] = feature_name
    report["design_version"] = design_version
    report["updated_at"] = datetime.now(timezone.utc).isoformat()
    report[gate_name] = payload

    content = json.dumps(report, ensure_ascii=False, indent=2)
    last_error: OSError | None = None
    for _ in range(3):
        try:
            report_path.write_text(content, encoding="utf-8")
            return report_path
        except OSError as exc:
            last_error = exc
            time.sleep(0.05)
    if last_error is not None:
        raise last_error
    return report_path
