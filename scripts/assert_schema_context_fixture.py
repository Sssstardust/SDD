#!/usr/bin/env python3
"""
Assert key fields in a generated schema-context fixture output.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("schema_context", help="generated schema-context.json path")
    parser.add_argument("--expected-source", required=True, help="expected source field")
    parser.add_argument("--expected-scenario", default=None, help="expected scenario field")
    parser.add_argument("--expected-table", action="append", default=None, help="expected table_name, repeatable")
    args = parser.parse_args()

    payload = json.loads(Path(args.schema_context).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        print("[FAIL] schema-context payload is not an object")
        return 1

    if payload.get("source") != args.expected_source:
        print(f"[FAIL] expected source={args.expected_source}, got {payload.get('source')}")
        return 1

    if args.expected_scenario is not None and payload.get("scenario") != args.expected_scenario:
        print(f"[FAIL] expected scenario={args.expected_scenario}, got {payload.get('scenario')}")
        return 1

    expected_tables = args.expected_table or []
    actual_tables = [
        str(item.get("table_name"))
        for item in payload.get("tables", [])
        if isinstance(item, dict) and isinstance(item.get("table_name"), str)
    ]
    for table_name in expected_tables:
        if table_name not in actual_tables:
            print(f"[FAIL] expected table not found: {table_name}")
            return 1

    print("[OK] schema-context fixture assertion passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
