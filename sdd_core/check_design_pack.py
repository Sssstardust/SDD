#!/usr/bin/env python3
"""
SDD Architecture Guard: Check Design Pack.
Verifies that the design pack contents align with capability tags.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

def check_pack(feature_brief_path: Path) -> list[str]:
    if not feature_brief_path.exists():
        return [f"需求规格文件不存在: {feature_brief_path}"]
        
    workspace = feature_brief_path.parent
    structured_prd_path = workspace / "structured-prd.json"
    design_pack_dir = workspace / "design-pack"
    
    if not structured_prd_path.exists():
        return [f"缺少 structured-prd.json"]
        
    with structured_prd_path.open(encoding="utf-8") as f:
        prd = json.load(f)
        
    tags = prd.get("capability_tags", [])
    errors = []
    
    if not design_pack_dir.exists() or not design_pack_dir.is_dir():
        return ["缺少 design-pack 目录"]
        
    # Check for mandatory files based on tags
    if "api" in tags:
        if not (design_pack_dir / "接口契约.openapi.yaml").exists():
            errors.append("缺少 design-pack 文件: 接口契约.openapi.yaml (由 api 标签要求)")
            
    if "db-change" in tags:
        if not (design_pack_dir / "数据库变更.sql").exists():
            errors.append("缺少 design-pack 文件: 数据库变更.sql (由 db-change 标签要求)")
            
    return errors

def main():
    if len(sys.argv) < 2:
        print("Usage: check_design_pack.py <feature_brief_file>")
        sys.exit(1)
        
    feature_brief = Path(sys.argv[1])
    errors = check_pack(feature_brief)
    
    if errors:
        for err in errors:
            print(f"- {err}")
        sys.exit(1)
        
    print("[OK] Design pack is valid.")
    sys.exit(0)

if __name__ == "__main__":
    main()
