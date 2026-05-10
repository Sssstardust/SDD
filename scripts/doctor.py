#!/usr/bin/env python3
"""
Cross-platform doctor entrypoint.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from application.doctor_runtime import run_doctor
from infrastructure.doctor_checks import (
    count_baseline_buckets,
    find_security_warnings,
    path_required,
    run_capture,
    run_mcp_smoke,
    test_json_file,
    test_version,
    validate_attachment_shape,
)

ROOT = Path(__file__).resolve().parent.parent


def print_check(level: str, message: str) -> None:
    print(f"[{level}] {message}")



def run_polyquery_governance(root: Path) -> tuple[bool, str]:
    script = root / "scripts" / "check_polyquery_config.py"
    if not script.exists():
        return False, f"polyquery governance script is missing: {script}"
    exit_code, output = run_capture(["python", str(script), "--config", str(root / "config" / "polyquery.example.json")], cwd=root)
    if exit_code == 0:
        return True, output or "polyquery governance passed"
    return False, output or "polyquery governance failed"


def emit_json_result(status: str, sections: list[dict[str, object]]) -> None:
    print(json.dumps({"status": status, "sections": sections}, ensure_ascii=False))


def run_baseline_key_partition_governance(root: Path) -> tuple[bool, str]:
    script = root / "scripts" / "check_baseline_key_partition.py"
    if not script.exists():
        return False, f"baseline key partition script is missing: {script}"
    exit_code, output = run_capture(["python", str(script)], cwd=root)
    if exit_code == 0:
        return True, output or "baseline key partition validation passed"
    return False, output or "baseline key partition validation failed"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    parser.add_argument("--json", action="store_true", help="Emit structured JSON output instead of human-readable text.")
    args = parser.parse_args(argv)
    exit_code, sections, structured = run_doctor(
        root=ROOT,
        strict=args.strict,
        json_mode=args.json,
        print_check=print_check,
    )
    if args.json:
        status = "FAIL" if exit_code != 0 else "OK"
        if any(section["level"] == "WARN" for section in sections) and exit_code == 0:
            status = "WARN"
        emit_json_result(status, [*sections, {"section": "structured", "level": "INFO", "message": json.dumps(structured, ensure_ascii=False)}])
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
