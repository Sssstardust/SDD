#!/usr/bin/env python3
"""
refresh_module_map.py

通过 project-explorer 扫描器生成最小 module-map.json。
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from attached_project import DEFAULT_ATTACHMENT_PATH, component_id_for_path, resolve_module_map_scan_settings, source_signature
from baseline_paths import get_active_baseline_dir

ROOT = Path(__file__).resolve().parent.parent
BASELINE_DIR = get_active_baseline_dir(create=True, migrate_legacy=True)


def build_module_resource_key(item: dict[str, object], component_id: str | None) -> str:
    namespace = component_id or "default"
    fqn = item.get("fqn")
    if isinstance(fqn, str) and fqn:
        return f"{namespace}::{fqn}"
    source_file = str(item.get("source_file") or item.get("source_kind") or "unknown")
    simple_name = str(item.get("simple_name") or item.get("class_name") or "Anonymous")
    return f"{namespace}::{source_file}::{simple_name}"


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
    parser.add_argument("--force-refresh", action="store_true", help="忽略缓存并强制重新扫描")
    parser.add_argument("--project-root", default=None, help="显式目标项目根目录")
    parser.add_argument("--scan-root", action="append", default=None, help="显式扫描根目录，可重复传入")
    parser.add_argument("--design-root", action="append", default=None, help="显式设计根目录，可重复传入")
    parser.add_argument(
        "--attachment-file",
        default=str(DEFAULT_ATTACHMENT_PATH),
        help="附着目标项目配置文件路径，默认 .spec/attached-project.json",
    )
    parser.add_argument(
        "--output",
        default=str(BASELINE_DIR / "module-map.json"),
        help="输出 module-map.json 路径，默认写入 .spec/baseline/module-map.json",
    )
    args = parser.parse_args()

    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output)
    output_path = output_path if output_path.is_absolute() else (ROOT / output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    scan_settings = resolve_module_map_scan_settings(
        attachment_path=Path(args.attachment_file),
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
        raise RuntimeError("project-explorer Node/TS 运行入口不可用，请先确保 dist/server.js 存在并可执行")

    payload = annotate_module_map_payload(payload, scan_settings)
    payload.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
    payload.setdefault("scanner", "regex")
    payload.setdefault("evidence_level", "L2")
    payload.setdefault("confidence", "medium")
    payload.setdefault("unsupported_features", ["lombok-generated-methods", "mybatis-xml-mapping", "reflection", "framework-proxy"])
    payload.setdefault("ttl", "P1D")
    payload["source_signature"] = source_signature(scan_settings)
    payload["attachment"] = scan_settings
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[OK] module-map 快照已生成")
    print(f"  - file:  {output_path}")
    print(f"  - count: {len(payload['classes'])}")
    print(f"  - stats: {payload.get('source_stats', {})}")
    print(f"  - source:{scan_settings.get('source')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
