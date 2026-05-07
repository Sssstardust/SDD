#!/usr/bin/env python3
"""
Assert a JSON path contains an expected substring or item.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def resolve_path(payload: object, dotted_path: str) -> object:
    current = payload
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(dotted_path)
        current = current[part]
    return current


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("json_file", help="JSON file path")
    parser.add_argument("--path", required=True, help="dotted JSON path")
    parser.add_argument("--contains", required=True, help="expected substring or exact item")
    args = parser.parse_args()

    payload = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    actual = resolve_path(payload, args.path)
    expected = args.contains
    matched = False
    if isinstance(actual, str):
        matched = expected in actual
    elif isinstance(actual, list):
        matched = any(expected in item if isinstance(item, str) else item == expected for item in actual)

    if not matched:
        print(f"[FAIL] expected {args.path} to contain {expected!r}, got {actual!r}")
        return 1

    print(f"[OK] json contains assertion passed: {args.path} contains {expected!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
