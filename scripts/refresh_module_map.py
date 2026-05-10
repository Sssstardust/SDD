#!/usr/bin/env python3
"""
refresh_module_map.py

Generate the latest module-map.json through the project-explorer scanner.
"""

from __future__ import annotations

import argparse
import json
import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from domain.attached_project import (
    DEFAULT_ATTACHMENT_PATH,
    component_id_for_path,
    resolve_module_map_scan_settings,
    source_signature,
)
from infrastructure.baseline_paths import get_active_baseline_dir
from infrastructure.concurrency import atomic_write_text, path_lock


ROOT = Path(__file__).resolve().parent.parent


def build_module_resource_key(item: dict[str, object], component_id: str | None) -> str:
    namespace = component_id or "default"
    fqn = item.get("fqn")
    if isinstance(fqn, str) and fqn:
        return f"{namespace}::{fqn}"
    source_file = str(item.get("source_file") or item.get("source_kind") or "unknown")
    simple_name = str(item.get("simple_name") or item.get("class_name") or "Anonymous")
    return f"{namespace}::{source_file}::{simple_name}"


def source_signature(payload: dict[str, object]) -> str:
    relevant = {
        "source": payload.get("source"),
        "attachment": payload.get("attachment"),
        "component_ids": payload.get("component_ids", []),
        "classes": [
            {
                "resource_key": item.get("resource_key"),
                "component_id": item.get("component_id"),
                "source_file": item.get("source_file"),
            }
            for item in payload.get("classes", [])
            if isinstance(item, dict)
        ],
    }
    content = json.dumps(relevant, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def annotate_module_map_payload(payload: dict[str, object], scan_settings: dict[str, object]) -> dict[str, object]:
    classes = payload.get("classes")
    if not isinstance(classes, list):
        return payload

    annotated_classes: list[dict[str, object]] = []
    component_ids: set[str] = set()
    for item in classes:
        if not isinstance(item, dict):
            continue
        annotated = dict(item)
        component_id = component_id_for_path(
            annotated.get("source_file"),
            scan_settings,
            preferred_fields=("scan_roots", "design_roots"),
        )
        if component_id:
            annotated["component_id"] = component_id
            component_ids.add(component_id)
        annotated["resource_key"] = build_module_resource_key(annotated, component_id)
        annotated_classes.append(annotated)

    payload["classes"] = annotated_classes
    if component_ids:
        payload["component_ids"] = sorted(component_ids)
    return payload


def load_node_payload(force_refresh: bool, scan_roots: list[str] | None = None, design_roots: list[str] | None = None) -> dict | None:
    server_js = ROOT / "mcp-servers" / "project-explorer" / "dist" / "server.js"
    package_json = ROOT / "mcp-servers" / "project-explorer" / "package.json"
    if not server_js.exists() or not package_json.exists():
        return None

    arguments = {"force_refresh": force_refresh}
    if scan_roots:
        arguments["scan_roots"] = scan_roots
    if design_roots:
        arguments["design_roots"] = design_roots
    command = ["node", str(server_js), "--tool", "dump_module_map", "--arguments", json.dumps(arguments, ensure_ascii=False)]
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-refresh", action="store_true", help="Ignore cache and force a fresh scan.")
    parser.add_argument("--project-root", default=None, help="Explicit target project root")
    parser.add_argument("--scan-root", action="append", default=None, help="Explicit scan root, repeatable")
    parser.add_argument("--design-root", action="append", default=None, help="Explicit design root, repeatable")
    parser.add_argument(
        "--attachment-file",
        default=str(DEFAULT_ATTACHMENT_PATH),
        help="Attachment config path, defaults to .spec/attached-project.json",
    )
    parser.add_argument("--profile", default=None, help="Optional attachment profile name.")
    parser.add_argument("--output", default=None, help="Optional module-map.json output path")
    args = parser.parse_args()

    attachment_path = Path(args.attachment_file)
    baseline_dir = get_active_baseline_dir(
        attachment_path=attachment_path,
        profile=args.profile,
        create=True,
        migrate_legacy=True,
    )
    output_path = Path(args.output) if args.output else (baseline_dir / "module-map.json")
    output_path = output_path if output_path.is_absolute() else (ROOT / output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    scan_settings = resolve_module_map_scan_settings(
        attachment_path=attachment_path,
        profile=args.profile,
        scan_roots=[Path(item) for item in args.scan_root] if args.scan_root else None,
        design_roots=[Path(item) for item in args.design_root] if args.design_root else None,
        project_root=Path(args.project_root) if args.project_root else None,
    )
    payload = load_node_payload(
        args.force_refresh,
        scan_roots=[str(item) for item in scan_settings["scan_roots"]] if isinstance(scan_settings.get("scan_roots"), list) else None,
        design_roots=[str(item) for item in scan_settings["design_roots"]] if isinstance(scan_settings.get("design_roots"), list) else None,
    )
    if not isinstance(payload, dict):
        raise RuntimeError("project-explorer Node/TS entry is unavailable; please ensure dist/server.js exists and is runnable")

    payload = annotate_module_map_payload(payload, scan_settings)
    payload.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
    payload.setdefault("scanner", "regex")
    payload.setdefault("evidence_level", "L2")
    payload.setdefault("confidence", "medium")
    payload.setdefault("unsupported_features", ["lombok-generated-methods", "mybatis-xml-mapping", "reflection", "framework-proxy"])
    payload.setdefault("ttl", "P1D")
    payload["source_signature"] = source_signature({
        "source": scan_settings.get("source"),
        "attachment": scan_settings,
        "component_ids": payload.get("component_ids", []),
        "classes": payload.get("classes", []),
    })
    payload["attachment"] = scan_settings
    with path_lock(output_path, phase="refresh-module-map"):
        atomic_write_text(output_path, json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[OK] module-map snapshot generated")
    print(f"  - file:  {output_path}")
    print(f"  - count: {len(payload['classes'])}")
    print(f"  - stats: {payload.get('source_stats', {})}")
    print(f"  - source:{scan_settings.get('source')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
