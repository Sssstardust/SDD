#!/usr/bin/env python3
"""
sdd-validate: standalone Skill facade for SDD Gates.
Calls sdd_core.application.semantic_validate.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure sdd_core is importable
SKILL_DIR = Path(__file__).resolve().parent
ROOT = SKILL_DIR.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sdd_core.application.semantic_validate import run_validate


def load_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_payload_by_schema(instance: object, schema: dict, *, label: str) -> None:
    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(instance, dict):
            raise ValueError(f"{label} must be an object")
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if key not in instance:
                    raise ValueError(f"{label} missing required field: {key}")
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for key, child_schema in properties.items():
                if key in instance and isinstance(child_schema, dict):
                    validate_payload_by_schema(instance[key], child_schema, label=f"{label}.{key}")
        return
    if schema_type == "array":
        if not isinstance(instance, list):
            raise ValueError(f"{label} must be an array")
        child = schema.get("items")
        if isinstance(child, dict):
            for index, item in enumerate(instance):
                validate_payload_by_schema(item, child, label=f"{label}[{index}]")
        return
    if schema_type == "string":
        if not isinstance(instance, str):
            raise ValueError(f"{label} must be a string")
        return
    if schema_type == "boolean":
        if not isinstance(instance, bool):
            raise ValueError(f"{label} must be a boolean")
        return


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", help="feature 工作目录路径")
    parser.add_argument("--gates", action="append", help="指定要执行的 gate 名称")
    parser.add_argument("--strict", action="store_true", help="严格校验")
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    args = parser.parse_args()

    input_payload = {
        "workspace": args.workspace,
        "gates": args.gates or ["gate1", "gate2", "gate3"],
        "strict": args.strict,
        "attachment_file": args.attachment_file,
        "profile": args.profile,
    }
    
    validate_payload_by_schema(
        input_payload,
        load_schema(SKILL_DIR / "input.schema.json"),
        label="sdd-validate.input",
    )

    # 目前 sdd_core 内部已支持直接调用
    # 注意：semantic_validate.run_validate 内部目前可能还包含 subprocess，
    # 但我们已经在 sdd_core 层级统一了物理路径。
    exit_code = run_validate(
        feature_dir=args.workspace,
        gates=input_payload["gates"],
        strict=args.strict,
        attachment_file=args.attachment_file,
        profile=args.profile,
    )

    # 构造输出 Payload
    output_payload = {
        "status": "ok" if exit_code == 0 else "fail",
        "results": [
            {
                "gate": g,
                "success": exit_code == 0, # 这里简化了逻辑，实际应从 run_validate 获取明细
                "exit_code": exit_code
            } for g in input_payload["gates"]
        ],
        "summary": f"Validation finished with exit code {exit_code}"
    }

    validate_payload_by_schema(
        output_payload,
        load_schema(SKILL_DIR / "output.schema.json"),
        label="sdd-validate.output",
    )

    print(f"[OK] sdd-validate finished. Status: {output_payload['status']}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
