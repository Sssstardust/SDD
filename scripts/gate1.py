#!/usr/bin/env python3
"""
Gate 1: design structure and design-pack completeness.
"""

from __future__ import annotations

import argparse
import json
import locale
import re
import subprocess
import sys
from pathlib import Path

from ambiguity_tracker import sync_ambiguity_tracker
from concurrency import atomic_write_text
from design_evidence import freeze_design_pack, hash_file, hash_tree
from gate_report import build_violations, write_gate_section
from versioning import detect_latest_design_path, reports_dir_for_design, resolve_feature_dir


ROOT = Path(__file__).resolve().parent.parent


def extract_yaml_blocks(text: str) -> list[str]:
    matches = re.findall(r"```yaml\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return matches if matches else [text]


def extract_scalar(yaml_text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", yaml_text)
    if not match:
        return None
    return match.group(1).strip().strip('"').strip("'")


def run_check(label: str, command: list[str]) -> dict[str, object]:
    result = subprocess.run(
        command,
        check=False,
        cwd=str(ROOT),
        capture_output=True,
    )
    preferred_encoding = locale.getpreferredencoding(False) or "utf-8"

    def decode_output(value: bytes) -> str:
        for encoding in ("utf-8", preferred_encoding, "gbk"):
            try:
                return value.decode(encoding)
            except UnicodeDecodeError:
                continue
        return value.decode("utf-8", errors="replace")

    output = "\n".join(
        part
        for part in [decode_output(result.stdout).strip(), decode_output(result.stderr).strip()]
        if part
    )
    return {
        "label": label,
        "command": command,
        "returncode": result.returncode,
        "output": output,
    }


def gate1(feature_dir: Path) -> dict[str, object]:
    feature_brief = feature_dir / "feature-brief.md"
    design_path = detect_latest_design_path(feature_dir)

    errors: list[str] = []
    checks: list[str] = []
    warnings: list[str] = []
    command_results: list[dict[str, object]] = []
    ambiguity_tracker_path: str | None = None

    if not feature_brief.exists():
        errors.append(f"missing feature-brief.md: {feature_brief}")
    if not design_path.exists():
        errors.append(f"missing design document: {design_path}")

    feature_name = feature_dir.name
    if feature_brief.exists():
        yaml_text = "\n".join(extract_yaml_blocks(feature_brief.read_text(encoding="utf-8", errors="ignore")))
        feature_name = extract_scalar(yaml_text, "feature_name") or feature_name
        tracker = sync_ambiguity_tracker(feature_dir)
        ambiguity_tracker_path = str(feature_dir / "ambiguity-tracker.json")
        items = tracker.get("items")
        if isinstance(items, list):
            open_items = [item for item in items if isinstance(item, dict) and item.get("status") == "open"]
            resolved_count = int(tracker.get("resolved_count", 0))
            waived_count = int(tracker.get("waived_count", 0))
            if resolved_count or waived_count:
                warnings.append(
                    f"ambiguity tracker contains {resolved_count} resolved and {waived_count} waived items"
                )
            for item in open_items:
                errors.append(f"open ambiguity {item.get('id')}: {item.get('text')}")

    if not errors:
        command_results.append(
            run_check(
                "check-design",
                [sys.executable, str(ROOT / "scripts" / "check_design_structure.py"), str(design_path)],
            )
        )
        command_results.append(
            run_check(
                "check-design-pack",
                [sys.executable, str(ROOT / "scripts" / "check_design_pack.py"), str(feature_brief)],
            )
        )

    for command_result in command_results:
        label = str(command_result["label"])
        if int(command_result["returncode"]) == 0:
            checks.append(label)
            continue
        output = str(command_result.get("output") or "").strip()
        errors.append(f"{label} failed: {output or 'no output'}")

    reports_dir = reports_dir_for_design(feature_dir, design_path)
    result = "PASS" if not errors else "FAIL"
    snapshot_dir = freeze_design_pack(feature_dir, reports_dir) if result == "PASS" else None
    payload = {
        "result": result,
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
        "commands": command_results,
        "ambiguity_tracker": ambiguity_tracker_path,
        "design_pack_snapshot": str(snapshot_dir) if snapshot_dir else None,
        "evidence": {
            "design_hash": hash_file(design_path),
            "design_pack_hash": hash_tree(snapshot_dir or (feature_dir / "design-pack")),
            "evidence_level": "L3",
            "confidence": "medium",
        },
    }
    payload["violations"] = build_violations("gate1", payload)
    gate_report_path = write_gate_section(
        reports_dir,
        gate_name="gate1",
        feature_name=feature_name,
        design_version=design_path.name,
        payload=payload,
    )
    sidecar_report_path = reports_dir / "gate1-report.json"
    sidecar_payload = {
        "feature_name": feature_name,
        "design_version": design_path.name,
        **payload,
        "violations": payload.get("violations", []),
        "gate_report": str(gate_report_path),
    }
    atomic_write_text(
        sidecar_report_path,
        json.dumps(sidecar_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    payload["report_file"] = str(sidecar_report_path)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_dir", help="Path to specs/<feature>")
    args = parser.parse_args()

    result = gate1(resolve_feature_dir(args.feature_dir))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
