#!/usr/bin/env python3
"""
Validate PolyQuery configuration governance rules.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def load_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def validate_polyquery_config(config: dict[str, object]) -> tuple[list[str], list[str]]:
    checks: list[str] = []
    errors: list[str] = []
    if not config:
        errors.append("polyquery config is missing or invalid")
        return checks, errors

    if config.get("enabled") is not True:
        errors.append("polyquery config must set enabled=true")

    mcp = config.get("mcp")
    if not isinstance(mcp, dict):
        errors.append("polyquery config missing mcp object")
        return checks, errors

    command = mcp.get("command")
    args = mcp.get("args")
    timeout_seconds = mcp.get("timeout_seconds")
    env = mcp.get("env")
    if not isinstance(command, str) or not command:
        errors.append("polyquery.mcp.command must be a non-empty string")
    if not isinstance(args, list) or not all(isinstance(item, str) and item for item in args):
        errors.append("polyquery.mcp.args must be a list of non-empty strings")
    else:
        checks.append("polyquery.mcp.args is well-formed")
    if not isinstance(timeout_seconds, (int, float)) or timeout_seconds <= 0:
        errors.append("polyquery.mcp.timeout_seconds must be positive")
    if not isinstance(env, dict):
        errors.append("polyquery.mcp.env must be an object")
        return checks, errors

    readonly = str(env.get("READ_ONLY_MODE") or "").lower()
    if readonly != "true":
        errors.append("polyquery.mcp.env.READ_ONLY_MODE must be true")
    else:
        checks.append("polyquery.mcp.env.READ_ONLY_MODE is true")

    for key in ("POSTGRES_CONFIGS", "ORACLE_CONFIGS", "MYSQL_CONFIGS"):
        value = env.get(key)
        if value is None:
            continue
        if not isinstance(value, dict):
            errors.append(f"polyquery.mcp.env.{key} must be an object")
            continue
        for name, dsn in value.items():
            if not isinstance(name, str) or not isinstance(dsn, str) or not dsn:
                errors.append(f"polyquery.mcp.env.{key}.{name} must be a string DSN")
                continue
            if not dsn.startswith(("postgresql://readonly:${", "oracle://readonly:${", "mysql://readonly:${")):
                errors.append(f"polyquery.mcp.env.{key}.{name} must use readonly placeholder DSN")

    discovery = config.get("discovery")
    if not isinstance(discovery, dict):
        errors.append("polyquery config missing discovery object")
    else:
        max_tables = discovery.get("max_tables")
        on_ambiguous = discovery.get("on_ambiguous")
        if not isinstance(max_tables, int) or max_tables <= 0:
            errors.append("polyquery.discovery.max_tables must be a positive integer")
        elif max_tables > 30:
            errors.append("polyquery.discovery.max_tables should not exceed 30 for governance baseline")
        else:
            checks.append("polyquery.discovery.max_tables is within governance baseline")
        if on_ambiguous != "require-confirmation":
            errors.append('polyquery.discovery.on_ambiguous must be "require-confirmation"')
        else:
            checks.append("polyquery.discovery.on_ambiguous is require-confirmation")

    return checks, errors


def validate_polyquery_example(example_path: Path) -> tuple[list[str], list[str]]:
    config = load_json(example_path)
    checks, errors = validate_polyquery_config(config)
    if not checks and not errors:
        errors.append("polyquery example config could not be parsed")
    return checks, errors


def find_cleartext_dsn_issues(root: Path) -> list[str]:
    issues: list[str] = []
    config_path = root / "config" / "polyquery.json"
    if not config_path.exists():
        return issues
    text = config_path.read_text(encoding="utf-8", errors="ignore")
    if re.search(r"postgresql://[^$][^\s\"']+|mysql://[^$][^\s\"']+|oracle://[^$][^\s\"']+", text):
        issues.append("polyquery.json may contain a cleartext DSN instead of placeholder/env substitution")
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default=str(ROOT / "config" / "polyquery.example.json"),
        help="PolyQuery example config to validate.",
    )
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    checks, errors = validate_polyquery_example(config_path)
    for issue in find_cleartext_dsn_issues(ROOT):
        errors.append(issue)

    if errors:
        print("[FAIL] polyquery configuration governance failed")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("[OK] polyquery configuration governance passed")
    for check in checks:
        print(f"  - {check}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
