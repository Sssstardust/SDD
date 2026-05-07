#!/usr/bin/env python3
"""
doctor_smoke.py

Run a lightweight gate smoke test against a bundled fixture feature.
The fixture is copied to a temporary workspace first so doctor checks
do not mutate tracked reports under examples/fixtures/.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from fixture_matrix import build_workspace_root, prepare_feature_fixture


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FIXTURE = ROOT / "examples" / "fixtures" / "lightweight-api-smoke"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def build_commands(feature_dir: Path) -> list[list[str]]:
    runner = ROOT / "scripts" / "run_pipeline.py"
    return [
        [sys.executable, str(runner), "release-gate", str(feature_dir)],
        [sys.executable, str(runner), "validate-reports", str(feature_dir), "--stage", "implementation"],
    ]


def prepare_workspace(fixture_dir: Path, workspace_root: Path) -> Path:
    return prepare_feature_fixture(fixture_dir, workspace_root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE), help="fixture feature directory")
    parser.add_argument("--workspace", default=None, help="temporary workspace root")
    parser.add_argument("--keep-workdir", action="store_true", help="keep the copied smoke workspace")
    args = parser.parse_args()

    fixture_dir = Path(args.fixture).resolve()
    if not fixture_dir.exists():
        print(f"[FAIL] doctor smoke fixture is missing: {fixture_dir}")
        return 1

    temp_dir_path: str | None = None
    workspace_root: Path
    if args.workspace:
        workspace_root = Path(args.workspace).resolve()
        workspace_root.mkdir(parents=True, exist_ok=True)
    else:
        workspace_root = build_workspace_root(name="doctor-smoke")
        workspace_root.mkdir(parents=True, exist_ok=True)
        temp_dir_path = str(workspace_root)

    feature_dir = prepare_workspace(fixture_dir, workspace_root)
    print(f"[OK] prepared smoke fixture: {feature_dir}")

    try:
        for command in build_commands(feature_dir):
            result = run_command(command)
            print(f"$ {' '.join(command)}")
            if result.stdout.strip():
                print(result.stdout.strip())
            if result.stderr.strip():
                print(result.stderr.strip())
            if result.returncode != 0:
                print(f"[FAIL] command failed with exit code {result.returncode}")
                return result.returncode
    finally:
        if temp_dir_path and not args.keep_workdir:
            shutil.rmtree(temp_dir_path, ignore_errors=True)

    print("[OK] doctor gate smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
