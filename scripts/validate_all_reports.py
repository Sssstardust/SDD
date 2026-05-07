#!/usr/bin/env python3
"""
validate_all_reports.py

Validate reports for all feature directories that already have report artifacts.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from versioning import detect_latest_design_path, iter_feature_dirs, reports_dir_for_design


ROOT = Path(__file__).resolve().parent.parent


def console_print(message: str = "") -> None:
    payload = f"{message}\n"
    stream = sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    if hasattr(stream, "buffer"):
        stream.buffer.write(payload.encode(encoding, errors="replace"))
        stream.buffer.flush()
        return
    safe_payload = payload.encode(encoding, errors="replace").decode(encoding, errors="replace")
    stream.write(safe_payload)
    stream.flush()


def should_validate_feature(feature_dir: Path, *, require_verify: bool) -> tuple[bool, str]:
    design_path = detect_latest_design_path(feature_dir)
    reports_dir = reports_dir_for_design(feature_dir, design_path)
    gate_report = reports_dir / "gate-report.json"
    verify_report = reports_dir / "verify-report.json"

    if gate_report.exists() or verify_report.exists():
        if require_verify and not verify_report.exists():
            return False, f"缺少 verify-report.json: {verify_report}"
        return True, ""
    return False, "未找到 gate-report.json 或 verify-report.json，跳过未进入报告阶段的 feature"


def validate_feature(feature_dir: Path, stage: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_reports.py"), str(feature_dir), "--stage", stage],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
    return result.returncode, output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage",
        choices=["design", "implementation", "all"],
        default="all",
        help="校验阶段",
    )
    parser.add_argument(
        "--require-verify",
        action="store_true",
        help="要求所有正式 feature 都必须已有 verify-report.json",
    )
    args = parser.parse_args()

    errors: list[str] = []
    validated: list[str] = []
    skipped: list[str] = []

    for feature_dir in iter_feature_dirs():
        should_validate, reason = should_validate_feature(feature_dir, require_verify=args.require_verify)
        if not should_validate:
            if args.require_verify and "缺少 verify-report.json" in reason:
                errors.append(reason)
            else:
                skipped.append(f"{feature_dir.name}: {reason}")
            continue

        code, output = validate_feature(feature_dir, args.stage)
        if code != 0:
            errors.append(f"{feature_dir.name} 报告校验失败:\n{output}")
        else:
            validated.append(feature_dir.name)

    if errors:
        console_print("[FAIL] 全量 reports 复核失败")
        for error in errors:
            console_print(f"  - {error}")
        if skipped:
            console_print("[INFO] skipped:")
            for item in skipped:
                console_print(f"  - {item}")
        return 1

    console_print("[OK] 全量 reports 复核通过")
    console_print(f"  - stage: {args.stage}")
    console_print(f"  - validated: {', '.join(validated) if validated else '(none)'}")
    console_print(f"  - skipped: {len(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
