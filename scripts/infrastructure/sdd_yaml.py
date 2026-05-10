#!/usr/bin/env python3
"""
Small YAML loading helpers used by SDD scripts.
"""

from __future__ import annotations

import re
from typing import Any


def extract_yaml_blocks(text: str) -> list[str]:
    matches = re.findall(r"```yaml\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return matches if matches else [text]


def load_first_yaml_mapping(text: str) -> dict[str, Any]:
    for block in extract_yaml_blocks(text):
        data = load_yaml_mapping(block)
        if data:
            return data
    return {}


def load_yaml_documents(text: str) -> list[dict[str, Any]]:
    return [data for block in extract_yaml_blocks(text) if (data := load_yaml_mapping(block))]


def load_merged_yaml_mapping(text: str) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for data in load_yaml_documents(text):
        merged.update(data)
    return merged


def load_yaml_mapping(yaml_text: str) -> dict[str, Any]:
    try:
        import yaml  # type: ignore[import-not-found]

        loaded = yaml.safe_load(yaml_text)
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return parse_simple_yaml_mapping(yaml_text)


def parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if not value:
        return ""
    if "#" in value:
        quote_open = False
        cleaned = []
        quote_char = ""
        for char in value:
            if char in {"'", '"'}:
                if not quote_open:
                    quote_open = True
                    quote_char = char
                elif quote_char == char:
                    quote_open = False
            if char == "#" and not quote_open:
                break
            cleaned.append(char)
        value = "".join(cleaned).strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none", "~"}:
        return None
    if re.fullmatch(r"-?\d+", value):
        try:
            return int(value)
        except ValueError:
            return value
    if re.fullmatch(r"-?\d+\.\d+", value):
        try:
            return float(value)
        except ValueError:
            return value
    return value


def parse_simple_yaml_mapping(yaml_text: str) -> dict[str, Any]:
    lines: list[tuple[int, str]] = []
    for raw_line in yaml_text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        lines.append((len(raw_line) - len(raw_line.lstrip(" ")), raw_line.strip()))

    def parse_value(index: int, indent: int) -> tuple[Any, int]:
        if index >= len(lines) or lines[index][0] < indent:
            return {}, index
        if lines[index][0] == indent and lines[index][1].startswith("- "):
            return parse_list(index, indent)
        return parse_mapping(index, indent)

    def parse_mapping(index: int, indent: int) -> tuple[dict[str, Any], int]:
        result: dict[str, Any] = {}
        while index < len(lines):
            current_indent, stripped = lines[index]
            if current_indent < indent or stripped.startswith("- "):
                break
            if current_indent > indent:
                index += 1
                continue
            if ":" not in stripped:
                index += 1
                continue
            key, raw_value = stripped.split(":", 1)
            key = key.strip()
            if raw_value.strip():
                result[key] = parse_scalar(raw_value)
                index += 1
                continue
            index += 1
            if index < len(lines) and lines[index][0] > current_indent:
                result[key], index = parse_value(index, lines[index][0])
            else:
                result[key] = {}
        return result, index

    def parse_list(index: int, indent: int) -> tuple[list[Any], int]:
        result: list[Any] = []
        while index < len(lines):
            current_indent, stripped = lines[index]
            if current_indent != indent or not stripped.startswith("- "):
                break
            item_text = stripped[2:].strip()
            index += 1
            if re.match(r"^[A-Za-z_][A-Za-z0-9_-]*\s*:", item_text):
                key, raw_value = item_text.split(":", 1)
                item: dict[str, Any] = {}
                if raw_value.strip():
                    item[key.strip()] = parse_scalar(raw_value)
                elif index < len(lines) and lines[index][0] > current_indent:
                    item[key.strip()], index = parse_value(index, lines[index][0])
                else:
                    item[key.strip()] = {}
                if index < len(lines) and lines[index][0] > current_indent:
                    extra, index = parse_mapping(index, lines[index][0])
                    item.update(extra)
                result.append(item)
            else:
                result.append(parse_scalar(item_text))
                if index < len(lines) and lines[index][0] > current_indent:
                    _, index = parse_value(index, lines[index][0])
        return result, index

    parsed, _ = parse_mapping(0, lines[0][0] if lines else 0)
    return parsed


def get_scalar(data: dict[str, Any], key: str, default: str | None = None) -> str | None:
    value = data.get(key)
    if value is None:
        return default
    return str(value)


def get_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key)
    if isinstance(value, list):
        return [str(item) for item in value]
    return []

