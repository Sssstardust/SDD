#!/usr/bin/env python3
"""
SDD Architecture Guard: Check Design Structure.
Verifies that the design document contains all required chapters.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REQUIRED_CHAPTERS = [
    r"^# 技术设计方案",
    r"^## 1\. 设计概述",
    r"^## 2\. 领域模型映射",
    r"^## 3\. 核心流程",
    r"^## 4\. 接口契约",
    r"^## 5\. 数据库变更",
    r"^## 6\. 异常处理",
    r"^## 7\. 架构约束自查",
    r"^## 8\. 验收标准矩阵",
    r"^## 9\. 设计包引用",
]

def check_structure(file_path: Path) -> list[str]:
    if not file_path.exists():
        return [f"设计文件不存在: {file_path}"]
    
    content = file_path.read_text(encoding="utf-8")
    errors = []
    
    for chapter_regex in REQUIRED_CHAPTERS:
        if not re.search(chapter_regex, content, re.MULTILINE):
            errors.append(f"缺少章节: {chapter_regex}")
            
    return errors

def main():
    if len(sys.argv) < 2:
        print("Usage: check_design_structure.py <design_file>")
        sys.exit(1)
        
    design_file = Path(sys.argv[1])
    errors = check_structure(design_file)
    
    if errors:
        for err in errors:
            print(f"- {err}")
        sys.exit(1)
        
    print("[OK] Design structure is valid.")
    sys.exit(0)

if __name__ == "__main__":
    main()
