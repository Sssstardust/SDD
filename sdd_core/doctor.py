#!/usr/bin/env python3
"""
Cross-platform doctor entrypoint.
"""

from __future__ import annotations

from typing import Any

import argparse
import json
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from sdd_core.application.doctor_runtime import run_doctor
from sdd_core.application.gates.gate_runtime import check_baseline_keys as check_baseline_keys_runtime
from sdd_core.infrastructure.doctor_checks import (
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



def emit_json_result(status: str, sections: list[dict[str, Any]]) -> None:
    print(json.dumps({"status": status, "sections": sections}, ensure_ascii=False))


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
