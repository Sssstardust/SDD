#!/usr/bin/env python3
"""
Repository and reader protocols for Domain layer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class AttachmentConfigRepository(Protocol):
    def load(self, path: Path) -> dict[str, Any] | None: ...
    def save(self, path: Path, payload: dict[str, Any]) -> None: ...


class YamlReader(Protocol):
    def load_mapping(self, yaml_text: str) -> dict[str, Any]: ...
    def get_scalar(self, data: dict[str, Any], key: str, default: Any = None) -> Any: ...
    def get_list(self, data: dict[str, Any], key: str) -> list[Any]: ...
