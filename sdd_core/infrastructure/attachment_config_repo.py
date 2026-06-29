#!/usr/bin/env python3
"""
Infrastructure implementations of domain repositories and readers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from sdd_core.infrastructure.concurrency import atomic_write_text


class FileAttachmentConfigRepository:
    def load(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def save(self, path: Path, payload: dict[str, Any]) -> None:
        atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class InfrastructureYamlReader:
    def load_mapping(self, yaml_text: str) -> dict[str, Any]:
        from sdd_core.infrastructure.sdd_yaml import load_merged_yaml_mapping
        return load_merged_yaml_mapping(yaml_text)

    def get_scalar(self, data: dict[str, Any], key: str, default: Any = None) -> Any:
        from sdd_core.infrastructure.sdd_yaml import get_scalar
        return get_scalar(data, key, default)

    def get_list(self, data: dict[str, Any], key: str) -> list[Any]:
        from sdd_core.infrastructure.sdd_yaml import get_list
        return get_list(data, key)
