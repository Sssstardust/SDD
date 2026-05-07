#!/usr/bin/env python3
"""
Assert a JSON path equals an expected JSON literal or string.
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


def parse_expected(raw: str) -> object:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("json_file", help="JSON file path")
    parser.add_argument("--path", required=True, help="dotted JSON path")
    parser.add_argument("--equals", required=True, help="expected value, JSON literal or string")
    args = parser.parse_args()

    payload = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    actual = resolve_path(payload, args.path)
    expected = parse_expected(args.equals)
    if actual != expected:
        print(f"[FAIL] expected {args.path}={expected!r}, got {actual!r}")
        return 1
    print(f"[OK] json assertion passed: {args.path}={expected!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
