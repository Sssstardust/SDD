#!/usr/bin/env python3
"""
onboard_attached_project.py

Initialize an attached project into a runnable SDD workspace:
- save attached config
- refresh baseline snapshots
- build project console artifacts
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from attached_project import (
    DEFAULT_ATTACHMENT_PATH,
    build_attachment_payload,
    load_attachment_seed,
    save_attachment_config,
    validate_components_for_risk_tier,
)
from baseline_paths import get_active_baseline_dir
from project_artifact_paths import get_active_project_artifacts_dir


ROOT = Path(__file__).resolve().parent.parent


def build_onboarding_commands(attachment_file: Path) -> list[list[str]]:
    baseline_dir = get_active_baseline_dir(attachment_path=attachment_file, create=True, migrate_legacy=True)
    artifacts_dir = get_active_project_artifacts_dir(attachment_path=attachment_file, create=True)
    return [
        [sys.executable, str(ROOT / "scripts" / "refresh_module_map.py"), "--attachment-file", str(attachment_file)],
        [sys.executable, str(ROOT / "scripts" / "refresh_schema_context.py"), "--attachment-file", str(attachment_file)],
        [sys.executable, str(ROOT / "scripts" / "refresh_baseline_governance.py"), "--baseline-dir", str(baseline_dir)],
        [sys.executable, str(ROOT / "scripts" / "refresh_project_state.py")],
        [sys.executable, str(ROOT / "scripts" / "build_project_console.py"), "--output-dir", str(artifacts_dir)],
    ]


def default_runner(command: list[str]) -> int:
    result = subprocess.run(command, check=False, cwd=str(ROOT))
    return result.returncode


def run_onboarding(
    *,
    project_root: Path | None = None,
    attachment_file: Path = DEFAULT_ATTACHMENT_PATH,
    name: str | None = None,
    profile: str | None = None,
    project_id: str | None = None,
    design_roots: list[Path] | None = None,
    schema_roots: list[Path] | None = None,
    components: list[dict[str, object]] | None = None,
    extra_fields: dict[str, object] | None = None,
    runner=default_runner,
) -> dict[str, object]:
    payload = build_attachment_payload(
        project_root=project_root,
        name=name,
        design_roots=design_roots,
        schema_roots=schema_roots,
        components=components,
        extra_fields=extra_fields,
    )
    for warning in validate_components_for_risk_tier(
        payload.get("components") if isinstance(payload.get("components"), list) else None,
        str(payload.get("risk_tier") or "low"),
    ):
        print(warning)
    config_path = save_attachment_config(
        payload,
        attachment_file,
        profile=profile,
        project_id=project_id,
    )

    commands = build_onboarding_commands(config_path)
    step_names = [
        "refresh-module-map",
        "refresh-schema-context",
        "refresh-baseline-governance",
        "refresh-project-state",
        "build-project-console",
    ]
    for step_name, command in zip(step_names, commands):
        code = runner(command)
        if code != 0:
            return {
                "result": "fail",
                "failed_step": step_name,
                "exit_code": code,
                "attachment_file": str(config_path),
            }

    return {
        "result": "ok",
        "attachment_file": str(config_path),
        "baseline_dir": str(get_active_baseline_dir(attachment_path=config_path, create=True, migrate_legacy=True)),
        "project_artifacts_dir": str(get_active_project_artifacts_dir(attachment_path=config_path, create=True)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=None, help="Target project root")
    parser.add_argument("--name", default=None, help="Attached project display name")
    parser.add_argument("--profile", default=None, help="Attachment profile name")
    parser.add_argument("--project-id", default=None, help="Explicit project_id, otherwise derived from name + project_root")
    parser.add_argument("--design-root", action="append", default=None, help="Explicit design root, repeatable")
    parser.add_argument("--schema-root", action="append", default=None, help="Explicit schema root, repeatable")
    parser.add_argument("--components-file", default=None, help="JSON file containing components[] or a full payload")
    parser.add_argument(
        "--attachment-file",
        default=str(DEFAULT_ATTACHMENT_PATH),
        help="Attachment compatibility file path, defaults to .spec/attached-project.json",
    )
    args = parser.parse_args()

    seed_payload = load_attachment_seed(Path(args.components_file)) if args.components_file else {}
    try:
        result = run_onboarding(
            project_root=Path(args.project_root) if args.project_root else None,
            attachment_file=Path(args.attachment_file),
            name=args.name,
            profile=args.profile,
            project_id=args.project_id,
            design_roots=[Path(item) for item in args.design_root] if args.design_root else None,
            schema_roots=[Path(item) for item in args.schema_root] if args.schema_root else None,
            components=seed_payload.get("components") if isinstance(seed_payload.get("components"), list) else None,
            extra_fields=seed_payload,
        )
    except ValueError as exc:
        print(f"[FAIL] attached project onboarding failed: {exc}")
        return 1

    if result["result"] != "ok":
        print("[FAIL] attached project onboarding failed")
        print(f"  - step: {result['failed_step']}")
        print(f"  - code: {result['exit_code']}")
        print(f"  - file: {result['attachment_file']}")
        return 1

    print("[OK] attached project onboarding completed")
    print(f"  - attachment: {result['attachment_file']}")
    print(f"  - baseline:   {result['baseline_dir']}")
    print(f"  - artifacts:  {result['project_artifacts_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
