#!/usr/bin/env python3
"""
Gate report writing helpers.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .concurrency import atomic_write_text, feature_lock
from domain.gate_report import GateSection


def build_violations(gate_name: str, payload: dict) -> list[dict[str, object]]:
    return GateSection.from_payload(gate_name, payload).to_payload()["violations"]


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
        gate_section = GateSection.from_payload(gate_name, payload)
        report[gate_name] = gate_section.to_payload()

        atomic_write_text(report_path, json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report_path

