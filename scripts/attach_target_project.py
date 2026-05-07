#!/usr/bin/env python3
"""
attach_target_project.py

保存、查看或清理当前附着目标项目配置。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from attached_project import (
    DEFAULT_ATTACHMENT_PATH,
    build_attachment_payload,
    load_attachment_config,
    load_attachment_seed,
    save_attachment_config,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=None, help="目标项目根目录")
    parser.add_argument("--name", default=None, help="附着项目显示名称")
    parser.add_argument("--scan-root", action="append", default=None, help="显式扫描根目录，可重复传入")
    parser.add_argument("--design-root", action="append", default=None, help="显式设计根目录，可重复传入")
    parser.add_argument("--schema-root", action="append", default=None, help="显式 schema 根目录，可重复传入")
    parser.add_argument("--components-file", default=None, help="JSON 文件，支持 components[] 或完整 attached-project payload")
    parser.add_argument("--show", action="store_true", help="仅显示当前附着配置")
    parser.add_argument("--clear", action="store_true", help="清空当前附着配置")
    args = parser.parse_args()

    if args.show:
        payload = load_attachment_config(DEFAULT_ATTACHMENT_PATH)
        if payload is None:
            print("[OK] 当前未配置附着目标项目")
            return 0
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.clear:
        if DEFAULT_ATTACHMENT_PATH.exists():
            DEFAULT_ATTACHMENT_PATH.unlink()
            print(f"[OK] 已清空附着配置: {DEFAULT_ATTACHMENT_PATH}")
        else:
            print("[OK] 当前未配置附着目标项目")
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

    config_path = save_attachment_config(payload, DEFAULT_ATTACHMENT_PATH)
    print("[OK] 已保存附着目标项目配置")
    print(f"  - file:        {config_path}")
    print(f"  - name:        {payload['name']}")
    print(f"  - project:     {payload.get('project_root', '<component-only>')}")
    print(f"  - scan_roots:  {', '.join(payload['scan_roots'])}")
    print(f"  - design_roots:{', '.join(payload['design_roots'])}")
    print(f"  - schema_roots:{', '.join(payload['schema_roots'])}")
    if payload.get("components"):
        print(f"  - components:  {len(payload['components'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
