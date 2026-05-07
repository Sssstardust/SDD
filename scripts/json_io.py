#!/usr/bin/env python3
"""
json_io.py

统一处理 JSON 文件读写，兼容 Windows 编辑器可能写入的 UTF-8 BOM。
"""

from __future__ import annotations

import json
from pathlib import Path


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8-sig"))
