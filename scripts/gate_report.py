#!/usr/bin/env python3
"""
gate_report.py

维护 reports/v{N}/gate-report.json。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from concurrency import atomic_write_text, feature_lock


def build_violations(gate_name: str, payload: dict) -> list[dict[str, object]]:
    existing = payload.get("violations")
    if isinstance(existing, list):
        return existing

    violations: list[dict[str, object]] = []
    location = payload.get("report_file")
    for severity, key in (("error", "errors"), ("warn", "warnings")):
        items = payload.get(key)
        if not isinstance(items, list):
            continue
        for index, detail in enumerate(items, start=1):
            violations.append(
                {
                    "rule": f"{gate_name}-{severity}-{index:03d}",
                    "severity": severity,
                    "location": location,
                    "detail": str(detail),
                }
            )
    return violations


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
    feature_dir = reports_dir.parent.parent

    with feature_lock(feature_dir, phase=f"gate-report:{gate_name}"):
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
        normalized_payload = dict(payload)
        normalized_payload["violations"] = build_violations(gate_name, normalized_payload)
        report[gate_name] = normalized_payload

        atomic_write_text(report_path, json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report_path
