#!/usr/bin/env python3
"""
check_arch_standards_sync.py

校验架构规范的文档事实源与 MCP 打包副本是否同步。
"""

from __future__ import annotations

import filecmp
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs" / "arch-standards"
MCP_RULES_DIR = ROOT / "mcp-servers" / "arch-standard" / "rules"
SYNC_SUFFIXES = {".md", ".json"}


def comparable_files(directory: Path) -> dict[str, Path]:
    if not directory.exists():
        return {}
    return {
        path.name: path
        for path in sorted(directory.iterdir())
        if path.is_file() and path.suffix.lower() in SYNC_SUFFIXES
    }


def main() -> int:
    docs_files = comparable_files(DOCS_DIR)
    mcp_files = comparable_files(MCP_RULES_DIR)
    errors: list[str] = []

    if not docs_files:
        errors.append(f"docs arch standards directory is empty or missing: {DOCS_DIR}")
    if not mcp_files:
        errors.append(f"MCP arch rules directory is empty or missing: {MCP_RULES_DIR}")

    for name in sorted(set(docs_files) - set(mcp_files)):
        errors.append(f"MCP rules missing copy of docs arch standard: {name}")
    for name in sorted(set(mcp_files) - set(docs_files)):
        errors.append(f"docs arch standards missing source for MCP rule: {name}")
    for name in sorted(set(docs_files) & set(mcp_files)):
        if not filecmp.cmp(docs_files[name], mcp_files[name], shallow=False):
            errors.append(f"arch standard drift detected: {name}")

    if errors:
        print("[FAIL] arch standards sync check failed")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("[OK] arch standards sync check passed")
    print(f"  - docs: {DOCS_DIR}")
    print(f"  - mcp:  {MCP_RULES_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
