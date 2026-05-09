#!/usr/bin/env python3
"""
attach_target_project.py

Save, inspect, activate, or clear attached-project configuration.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from attached_project import (
    DEFAULT_ATTACHMENT_PATH,
    build_attachment_payload,
    build_workspace_payload,
    list_attachment_profiles,
    load_attachment_config,
    load_attachment_seed,
    remove_attachment_profile,
    save_attachment_config,
    set_active_attachment_profile,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=None, help="Target project root")
    parser.add_argument("--name", default=None, help="Attached project display name")
    parser.add_argument("--scan-root", action="append", default=None, help="Explicit scan root, repeatable")
    parser.add_argument("--design-root", action="append", default=None, help="Explicit design root, repeatable")
    parser.add_argument("--schema-root", action="append", default=None, help="Explicit schema root, repeatable")
    parser.add_argument("--components-file", default=None, help="JSON file containing components[] or a full payload")
    parser.add_argument("--profile", default=None, help="Attachment profile name")
    parser.add_argument("--project-id", default=None, help="Explicit project_id, otherwise derived from name + project_root")
    parser.add_argument("--list-profiles", action="store_true", help="List all saved attachment profiles")
    parser.add_argument("--activate-profile", default=None, help="Switch the active attachment profile")
    parser.add_argument("--show", action="store_true", help="Show the current or selected attachment config")
    parser.add_argument("--show-workspace", action="store_true", help="Show workspace.json style attachment summary")
    parser.add_argument("--clear", action="store_true", help="Clear attachment config or a selected profile")
    args = parser.parse_args()

    if args.list_profiles:
        print(json.dumps(list_attachment_profiles(DEFAULT_ATTACHMENT_PATH), ensure_ascii=False, indent=2))
        return 0

    if args.activate_profile:
        try:
            set_active_attachment_profile(args.activate_profile, DEFAULT_ATTACHMENT_PATH)
        except ValueError as exc:
            print(f"[ERROR] {exc}")
            return 1
        payload = load_attachment_config(DEFAULT_ATTACHMENT_PATH)
        print("[OK] active attachment profile switched")
        if isinstance(payload, dict):
            print(f"  - profile: {payload.get('profile')}")
            print(f"  - project_id: {payload.get('project_id')}")
            print(f"  - name: {payload.get('name')}")
        return 0

    if args.show:
        payload = load_attachment_config(DEFAULT_ATTACHMENT_PATH, profile=args.profile)
        if payload is None:
            print("[OK] no attached project is configured")
            return 0
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.show_workspace:
        print(json.dumps(build_workspace_payload(DEFAULT_ATTACHMENT_PATH), ensure_ascii=False, indent=2))
        return 0

    if args.clear:
        try:
            remove_attachment_profile(
                DEFAULT_ATTACHMENT_PATH,
                profile=args.profile,
                clear_all=args.profile is None,
            )
        except ValueError as exc:
            print(f"[ERROR] {exc}")
            return 1
        if args.profile:
            print(f"[OK] attachment profile cleared: {args.profile}")
        else:
            print(f"[OK] attachment config cleared: {DEFAULT_ATTACHMENT_PATH}")
        return 0

    seed_payload = load_attachment_seed(Path(args.components_file)) if args.components_file else {}
    try:
        payload = build_attachment_payload(
            project_root=Path(args.project_root) if args.project_root else None,
            name=args.name,
            scan_roots=[Path(item) for item in args.scan_root] if args.scan_root else None,
            design_roots=[Path(item) for item in args.design_root] if args.design_root else None,
            schema_roots=[Path(item) for item in args.schema_root] if args.schema_root else None,
            components=seed_payload.get("components") if isinstance(seed_payload.get("components"), list) else None,
            extra_fields=seed_payload,
        )
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 1

    config_path = save_attachment_config(
        payload,
        DEFAULT_ATTACHMENT_PATH,
        profile=args.profile,
        project_id=args.project_id,
    )
    saved_payload = load_attachment_config(DEFAULT_ATTACHMENT_PATH, profile=args.profile) or payload

    print("[OK] attached project config saved")
    print(f"  - file:        {config_path}")
    print(f"  - profile:     {saved_payload.get('profile')}")
    print(f"  - project_id:  {saved_payload.get('project_id')}")
    print(f"  - name:        {saved_payload['name']}")
    print(f"  - project:     {saved_payload.get('project_root', '<component-only>')}")
    print(f"  - scan_roots:  {', '.join(saved_payload['scan_roots'])}")
    print(f"  - design_roots:{', '.join(saved_payload['design_roots'])}")
    print(f"  - schema_roots:{', '.join(saved_payload['schema_roots'])}")
    if saved_payload.get("components"):
        print(f"  - components:  {len(saved_payload['components'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
