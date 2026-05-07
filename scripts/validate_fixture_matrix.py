#!/usr/bin/env python3
"""
Validate bundled example feature fixtures.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from fixture_matrix import build_workspace_root, discover_feature_fixtures, prepare_feature_fixture


ROOT = Path(__file__).resolve().parent.parent
RUN_PIPELINE = ROOT / "scripts" / "run_pipeline.py"

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


def format_parts(parts: list[str], *, feature_dir: Path, workspace_root: Path, source_dir: Path) -> list[str]:
    values = {
        "feature_dir": str(feature_dir),
        "workspace_root": str(workspace_root),
        "fixture_dir": str(feature_dir),
        "fixture_source_dir": str(source_dir),
        "repo_root": str(ROOT),
    }
    return [part.format(**values) for part in parts]


def command_spec(
    command: list[str],
    *,
    expected_exit_code: int = 0,
    expected_output_contains: list[str] | None = None,
) -> dict[str, object]:
    return {
        "command": command,
        "expected_exit_code": expected_exit_code,
        "expected_output_contains": expected_output_contains or [],
    }


def build_fixture_commands(feature_dir: Path, workspace_root: Path, source_dir: Path, manifest: dict[str, object]) -> list[dict[str, object]]:
    commands = manifest.get("commands")
    if not isinstance(commands, list) or not commands:
        return [
            command_spec(
                [sys.executable, str(RUN_PIPELINE), "validate-reports", str(feature_dir), "--stage", "implementation"]
            )
        ]

    built: list[dict[str, object]] = []
    for item in commands:
        if isinstance(item, list) and all(isinstance(part, str) for part in item) and item:
            parts = format_parts(item, feature_dir=feature_dir, workspace_root=workspace_root, source_dir=source_dir)
            built.append(command_spec([sys.executable, str(RUN_PIPELINE), parts[0], str(feature_dir), *parts[1:]]))
            continue
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "feature-command")
        raw_args = item.get("args")
        expected_exit_code = int(item.get("expected_exit_code", 0))
        expected_output_contains = [
            str(part)
            for part in item.get("expected_output_contains", [])
            if isinstance(part, str)
        ] if isinstance(item.get("expected_output_contains"), list) else []
        if not isinstance(raw_args, list) or not all(isinstance(part, str) for part in raw_args):
            continue
        args = format_parts(raw_args, feature_dir=feature_dir, workspace_root=workspace_root, source_dir=source_dir)
        if kind == "feature-command":
            if not args:
                continue
            built.append(
                command_spec(
                    [sys.executable, str(RUN_PIPELINE), args[0], str(feature_dir), *args[1:]],
                    expected_exit_code=expected_exit_code,
                    expected_output_contains=expected_output_contains,
                )
            )
        elif kind == "pipeline":
            built.append(
                command_spec(
                    [sys.executable, str(RUN_PIPELINE), *args],
                    expected_exit_code=expected_exit_code,
                    expected_output_contains=expected_output_contains,
                )
            )
        elif kind == "python-script":
            built.append(
                command_spec(
                    [sys.executable, *args],
                    expected_exit_code=expected_exit_code,
                    expected_output_contains=expected_output_contains,
                )
            )
    return built


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", action="append", default=None, help="fixture name to validate, repeatable")
    args = parser.parse_args()

    fixtures = discover_feature_fixtures()
    selected = set(args.fixture or [])
    if selected:
        fixtures = [item for item in fixtures if str(item.get("name")) in selected]
    if not fixtures:
        print("[FAIL] no fixture matched the requested filter")
        return 1

    for fixture in fixtures:
        fixture_name = str(fixture["name"])
        source_dir = Path(str(fixture["path"]))
        workspace_root = build_workspace_root(name=f"fixture-{fixture_name}")
        workspace_root.mkdir(parents=True, exist_ok=True)
        try:
            feature_dir = prepare_feature_fixture(source_dir, workspace_root)
            print(f"[INFO] validating fixture: {fixture_name}")
            for spec in build_fixture_commands(feature_dir, workspace_root, source_dir, fixture):
                command = spec["command"]
                expected_exit_code = int(spec.get("expected_exit_code", 0))
                expected_output_contains = [
                    str(item) for item in spec.get("expected_output_contains", []) if isinstance(item, str)
                ]
                result = run_command(command)
                print(f"$ {' '.join(command)}")
                if result.stdout.strip():
                    print(result.stdout.strip())
                if result.stderr.strip():
                    print(result.stderr.strip())
                combined_output = "\n".join(part for part in [result.stdout, result.stderr] if part)
                if result.returncode != expected_exit_code:
                    print(f"[FAIL] fixture validation failed: {fixture_name}")
                    print(f"  - expected exit: {expected_exit_code}")
                    print(f"  - actual exit:   {result.returncode}")
                    return 1
                for pattern in expected_output_contains:
                    if pattern not in combined_output:
                        print(f"[FAIL] fixture validation failed: {fixture_name}")
                        print(f"  - missing output pattern: {pattern}")
                        return 1
        finally:
            shutil.rmtree(workspace_root, ignore_errors=True)

    print(f"[OK] fixture matrix validation passed: {len(fixtures)} fixture(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
