#!/usr/bin/env python3
"""
sdd-assistant: The orchestrator skill for SDD.
Orchestrates: requirement-analyzer -> sdd-generation -> gate checks.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

SKILL_DIR = Path(__file__).resolve().parent
ROOT = SKILL_DIR.parents[1]

READY_EXIT_CODE = 0
SYSTEM_ERROR_EXIT_CODE = 1
CLARIFY_EXIT_CODE = 2


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


def run_command(command: list[str], label: str) -> subprocess.CompletedProcess:
    print(f"[ASSISTANT] Running {label}...")
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    if result.returncode != 0:
        print(f"[ERROR] {label} failed with exit code {result.returncode}")
        if result.stdout:
            print(f"STDOUT: {result.stdout}")
        if result.stderr:
            print(f"STDERR: {result.stderr}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_file", help="原始 PRD/需求文本路径")
    parser.add_argument("workspace", help="feature 工作目录")
    parser.add_argument("feature_name", help="feature 名称")
    parser.add_argument("--force", action="store_true", help="强制覆盖")
    parser.add_argument("--strict", action="store_true", help="严格校验")
    parser.add_argument("--no-ai", action="store_true", help="禁用 AI")
    args = parser.parse_args()

    input_payload = {
        "source_file": args.source_file,
        "workspace": args.workspace,
        "feature_name": args.feature_name,
        "force": args.force,
        "strict": args.strict,
        "no_ai": args.no_ai,
    }
    validate_payload_by_schema(
        input_payload,
        load_schema(SKILL_DIR / "input.schema.json"),
        label="sdd-assistant.input",
    )

    workspace = Path(args.workspace).resolve()
    source_file = Path(args.source_file).resolve()
    structured_prd = workspace / "structured-prd.json"
    feature_brief = workspace / "需求规格.md"
    design_doc = workspace / "技术方案.md"
    
    output_payload = {
        "status": "error",
        "workspace": str(workspace),
        "structured_prd": None,
        "design": None,
        "gate_results": [],
        "error_stage": None,
        "error_message": None,
    }

    # Step 1: Analyze
    analyzer_script = SKILL_DIR.parent / "requirement-analyzer" / "run.py"
    analyze_cmd = [
        sys.executable, str(analyzer_script),
        str(source_file), str(structured_prd),
        "--feature-brief-out", str(feature_brief),
        "--feature-name", args.feature_name
    ]
    if args.no_ai:
        analyze_cmd.append("--no-ai")
    
    res_analyze = run_command(analyze_cmd, "requirement-analyzer")
    if res_analyze.returncode != 0:
        output_payload.update({"error_stage": "analyze", "error_message": res_analyze.stderr or "Analyze failed"})
        validate_payload_by_schema(output_payload, load_schema(SKILL_DIR / "output.schema.json"), label="sdd-assistant.output")
        return SYSTEM_ERROR_EXIT_CODE
    
    output_payload["structured_prd"] = str(structured_prd)

    # Step 2: Generate
    generation_script = SKILL_DIR.parent / "sdd-generation" / "run.py"
    generate_cmd = [
        sys.executable, str(generation_script),
        "--workspace", str(workspace),
        "--output", str(design_doc)
    ]
    if args.force:
        generate_cmd.append("--force")
    if args.no_ai:
        generate_cmd.append("--no-ai")
    
    res_generate = run_command(generate_cmd, "sdd-generation")
    if res_generate.returncode != 0:
        output_payload.update({"error_stage": "generation", "error_message": res_generate.stderr or "Generation failed"})
        validate_payload_by_schema(output_payload, load_schema(SKILL_DIR / "output.schema.json"), label="sdd-assistant.output")
        return SYSTEM_ERROR_EXIT_CODE
    
    output_payload["design"] = str(design_doc)

    # Step 3: Gate Checks
    pipeline_script = ROOT / "sdd_core" / "run_pipeline.py"
    gates = ["gate2", "gate3"]
    gate_results = []
    all_gates_passed = True
    
    for gate in gates:
        gate_cmd = [sys.executable, str(pipeline_script), gate, str(workspace)]
        if args.strict:
            gate_cmd.append("--strict")
        
        res_gate = run_command(gate_cmd, f"pipeline-{gate}")
        gate_results.append({
            "gate": gate,
            "exit_code": res_gate.returncode,
            "success": res_gate.returncode == 0
        })
        if res_gate.returncode != 0:
            all_gates_passed = False

    output_payload["gate_results"] = gate_results
    output_payload["status"] = "ok" if all_gates_passed else "error"
    if not all_gates_passed:
        output_payload["error_stage"] = "validation"
        output_payload["error_message"] = "One or more gates failed"

    validate_payload_by_schema(
        output_payload,
        load_schema(SKILL_DIR / "output.schema.json"),
        label="sdd-assistant.output",
    )
    
    print(f"[OK] sdd-assistant orchestration finished. Status: {output_payload['status']}")
    return READY_EXIT_CODE if all_gates_passed else SYSTEM_ERROR_EXIT_CODE


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[FATAL] Orchestration failed: {e}")
        sys.exit(1)
