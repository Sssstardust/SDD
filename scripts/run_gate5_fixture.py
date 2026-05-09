#!/usr/bin/env python3
"""
Run Gate 5 for a fixture with overridable baseline and execution stubs.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import check_design_test_coverage


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_dir", help="fixture feature directory")
    parser.add_argument("--baseline-dir", required=True, help="baseline dir used by Gate 5")
    parser.add_argument(
        "--execution-status",
        choices=["PASS", "FAIL", "SKIPPED"],
        default="PASS",
        help="stubbed execution status for attempt_test_execution",
    )
    parser.add_argument("--strict", action="store_true", help="run Gate 5 in strict mode")
    args = parser.parse_args()

    baseline_dir = Path(args.baseline_dir).resolve()
    feature_dir = Path(args.feature_dir).resolve()
    original_baseline = check_design_test_coverage.get_active_baseline_dir
    original_execution = check_design_test_coverage.attempt_test_execution
    try:
        check_design_test_coverage.get_active_baseline_dir = lambda **_: baseline_dir
        check_design_test_coverage.attempt_test_execution = (
            lambda *_args, **_kwargs: {"status": args.execution_status, "mode": "fixture-stub"}
        )
        gate5_args = [str(feature_dir)]
        if args.strict:
            gate5_args.append("--strict")
        return check_design_test_coverage.main_for_args(gate5_args)
    finally:
        check_design_test_coverage.get_active_baseline_dir = original_baseline
        check_design_test_coverage.attempt_test_execution = original_execution


if __name__ == "__main__":
    raise SystemExit(main())
