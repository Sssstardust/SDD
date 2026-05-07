#!/usr/bin/env python3
"""
check_design_structure.py

最小可用设计文档结构校验：
- 必填章节存在
- 验收矩阵存在
- 引用了至少一个 design-pack 文件
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


REQUIRED_PATTERNS = [
    r"## 1\.\s*设计概述",
    r"## 2\.\s*领域模型映射",
    r"## 3\.\s*核心流程",
    r"## 4\.\s*接口契约",
    r"## 5\.\s*数据库变更",
    r"## 6\.\s*异常处理",
    r"## 7\.\s*架构约束自查",
    r"## 8\.\s*验收标准矩阵",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("design_file", help="design-vN.md 文件路径")
    args = parser.parse_args()

    path = Path(args.design_file)
    if not path.exists():
        print(f"[ERROR] 文件不存在: {path}")
        return 1

    text = path.read_text(encoding="utf-8")
    errors: list[str] = []

    for pattern in REQUIRED_PATTERNS:
        match = re.search(pattern, text)
        if not match:
            errors.append(f"缺少章节: {pattern}")
        else:
            # 检查章节内容密度：寻找下一个同级(##)或高级(#)标题，且必须在行首
            start_pos = match.end()
            remaining_text = text[start_pos:]
            # 仅匹配 # 或 ## 标題，排除 ### 及以下
            next_header = re.search(r"\n#{1,2} ", "\n" + remaining_text)
            content = remaining_text[:next_header.start()] if next_header else remaining_text
            
            meaningful_lines = [l.strip() for l in content.splitlines() if l.strip()]
            # 排除掉仅包含引用的行
            content_lines = [l for l in meaningful_lines if not l.startswith("引用") and not l.startswith("- 引用")]
            
            if len(content_lines) < 1:
                errors.append(f"章节内容缺失 (仅有标题或引用): {pattern}")

    if "REQ-ID" not in text:
        errors.append("缺少验收标准矩阵中的 REQ-ID 字段")

    if "design-pack/" not in text:
        errors.append("缺少 design-pack 引用")

    if errors:
        print("[FAIL] design 结构校验失败")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("[OK] design 结构校验通过")
    print(f"  - 文件: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
