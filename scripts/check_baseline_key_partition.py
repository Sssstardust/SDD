#!/usr/bin/env python3
"""
Validate baseline key partitioning and resource-key uniqueness.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from baseline_paths import get_active_baseline_dir


ROOT = Path(__file__).resolve().parent.parent


def load_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def validate_module_map(path: Path) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    payload = load_json(path)
    classes = payload.get("classes")
    if not isinstance(classes, list):
        errors.append(f"{path} missing classes array")
        return warnings, errors

    seen_keys: set[str] = set()
    component_ids: set[str] = set()
    duplicate_keys: list[str] = []
    for item in classes:
        if not isinstance(item, dict):
            continue
        resource_key = str(item.get("resource_key") or "").strip()
        component_id = str(item.get("component_id") or "").strip()
        if component_id:
            component_ids.add(component_id)
        if not resource_key:
            errors.append(f"{path} class entry missing resource_key: {item.get('simple_name') or item.get('class_name')}")
            continue
        if resource_key in seen_keys:
            duplicate_keys.append(resource_key)
        seen_keys.add(resource_key)

    if duplicate_keys:
        errors.append(f"{path} contains duplicate module-map resource_key values: {', '.join(sorted(set(duplicate_keys)))}")
    if not component_ids:
        warnings.append(f"{path} has no component_id annotations")
    recorded_component_ids = payload.get("component_ids")
    if isinstance(recorded_component_ids, list):
        recorded_set = {str(item).strip() for item in recorded_component_ids if str(item).strip()}
        if recorded_set and recorded_set != component_ids:
            errors.append(
                f"{path} component_ids do not match class component_id set: recorded={sorted(recorded_set)}, classes={sorted(component_ids)}"
            )
    return warnings, errors


def validate_schema_context(path: Path) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    payload = load_json(path)
    tables = payload.get("tables")
    if not isinstance(tables, list):
        errors.append(f"{path} missing tables array")
        return warnings, errors

    seen_keys: set[str] = set()
    duplicate_keys: list[str] = []
    for item in tables:
        if not isinstance(item, dict):
            continue
        component_id = str(item.get("component_id") or "").strip()
        resource_key = str(item.get("resource_key") or "").strip()
        if not component_id:
            warnings.append(f"{path} table entry missing component_id: {item.get('table_name')}")
        if not resource_key:
            errors.append(f"{path} table entry missing resource_key: {item.get('table_name')}")
            continue
        if resource_key in seen_keys:
            duplicate_keys.append(resource_key)
        seen_keys.add(resource_key)

    if duplicate_keys:
        errors.append(f"{path} contains duplicate schema-context resource_key values: {', '.join(sorted(set(duplicate_keys)))}")
    component_ids = {str(item.get("component_id") or "").strip() for item in tables if isinstance(item, dict) and str(item.get("component_id") or "").strip()}
    recorded_component_ids = payload.get("component_ids")
    if isinstance(recorded_component_ids, list):
        recorded_set = {str(item).strip() for item in recorded_component_ids if str(item).strip()}
        if recorded_set and recorded_set != component_ids:
            errors.append(
                f"{path} component_ids do not match table component_id set: recorded={sorted(recorded_set)}, tables={sorted(component_ids)}"
            )
    return warnings, errors


def validate_baseline_dir(baseline_dir: Path) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    module_map_path = baseline_dir / "module-map.json"
    schema_context_path = baseline_dir / "schema-context.json"
    module_warnings, module_errors = validate_module_map(module_map_path)
    schema_warnings, schema_errors = validate_schema_context(schema_context_path)
    warnings.extend(module_warnings)
    warnings.extend(schema_warnings)
    errors.extend(module_errors)
    errors.extend(schema_errors)
    return warnings, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--baseline-dir",
        default=None,
        help="Baseline directory to validate, defaults to the active attached-project baseline bucket.",
    )
    args = parser.parse_args(argv)

    baseline_dir = Path(args.baseline_dir) if args.baseline_dir else get_active_baseline_dir(create=True, migrate_legacy=True)
    warnings, errors = validate_baseline_dir(baseline_dir)

    if errors:
        print("[FAIL] baseline key partition validation failed")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("[OK] baseline key partition validation passed")
    for warning in warnings:
        print(f"  [WARN] {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
