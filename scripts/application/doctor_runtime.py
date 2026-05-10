#!/usr/bin/env python3
"""
Application-layer doctor runtime orchestration.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Callable

from infrastructure.doctor_checks import (
    count_baseline_buckets,
    find_security_warnings,
    path_required,
    run_capture,
    run_mcp_smoke,
    test_json_file,
    test_version,
    validate_attachment_shape,
)


def run_polyquery_governance(root: Path) -> tuple[bool, str]:
    script = root / "scripts" / "check_polyquery_config.py"
    if not script.exists():
        return False, f"polyquery governance script is missing: {script}"
    exit_code, output = run_capture(["python", str(script), "--config", str(root / "config" / "polyquery.example.json")], cwd=root)
    if exit_code == 0:
        return True, output or "polyquery governance passed"
    return False, output or "polyquery governance failed"


def run_baseline_key_partition_governance(root: Path) -> tuple[bool, str]:
    script = root / "scripts" / "check_baseline_key_partition.py"
    if not script.exists():
        return False, f"baseline key partition script is missing: {script}"
    exit_code, output = run_capture(["python", str(script)], cwd=root)
    if exit_code == 0:
        return True, output or "baseline key partition validation passed"
    return False, output or "baseline key partition validation failed"


def run_doctor(
    *,
    root: Path,
    strict: bool,
    json_mode: bool,
    print_check: Callable[[str, str], None],
) -> tuple[int, list[dict[str, object]], dict[str, object]]:
    has_failure = False
    has_warning = False
    sections: list[dict[str, object]] = []
    structured: dict[str, object] = {}

    def record(section: str, level: str, message: str) -> None:
        nonlocal has_failure, has_warning
        sections.append({"section": section, "level": level, "message": message})
        if level == "FAIL":
            has_failure = True
        elif level == "WARN":
            has_warning = True

    print("SDD Doctor")
    print(f"Repo: {root}")
    print()

    print("== Toolchain ==")
    python_ok, python_message = test_version("Python", ["python", "--version"], 3, 13)
    print_check("OK" if python_ok else "FAIL", python_message)
    record("toolchain", "OK" if python_ok else "FAIL", "Python")
    node_ok, node_message = test_version("Node.js", ["node", "--version"], 18, 0)
    print_check("OK" if node_ok else "FAIL", node_message)
    record("toolchain", "OK" if node_ok else "FAIL", "Node.js")
    structured["toolchain"] = {"python": python_ok, "node": node_ok}
    if shutil.which("javac"):
        exit_code, output = run_capture(["javac", "--version"])
        if exit_code == 0:
            print_check("OK", f"Java javac is available: {output}")
        else:
            print_check("WARN", f"javac exists, but version check failed: {output}")
            record("toolchain", "WARN", "javac")
    else:
        print_check("WARN", "javac was not found; Gate 5 Java verification may be unavailable.")
        record("toolchain", "WARN", "javac missing")

    print()
    print("== Workspace ==")
    workspace_results: list[dict[str, object]] = []
    for rel, description in [
        ("README.md", "README"),
        ("scripts/run_pipeline.py", "Pipeline entry"),
        ("skills/sdd-assistant/SKILL.md", "sdd-assistant Skill"),
        ("skills/requirement-analyzer/SKILL.md", "requirement-analyzer Skill"),
        ("skills/sdd-generation/SKILL.md", "sdd-generation Skill"),
        ("docs/agent-integration.md", "Agent integration doc"),
    ]:
        path_ok, path_message = path_required(root / rel, description)
        print_check("OK" if path_ok else "FAIL", path_message)
        workspace_results.append({"description": description, "ok": path_ok})
        if not path_ok:
            record("workspace", "FAIL", description)
    structured["workspace"] = workspace_results

    print()
    print("== MCP ==")
    mcp_results: list[dict[str, object]] = []
    for rel, description in [
        ("mcp-servers/project-explorer/dist/server.js", "project-explorer MCP dist"),
        ("mcp-servers/arch-standard/dist/server.js", "arch-standard MCP dist"),
    ]:
        path_ok, path_message = path_required(root / rel, description)
        print_check("OK" if path_ok else "FAIL", path_message)
        mcp_results.append({"description": description, "ok": path_ok})
        if not path_ok:
            record("mcp", "FAIL", description)
    ok, message = run_mcp_smoke(root, root / "mcp-servers/project-explorer/dist/server.js", "scan_modules", '{"keywords":["payment"],"limit":1,"force_refresh":false}')
    print_check("OK" if ok else "FAIL", message)
    record("mcp", "OK" if ok else "FAIL", "project-explorer scan_modules")
    ok, message = run_mcp_smoke(root, root / "mcp-servers/arch-standard/dist/server.js", "list_rules", "{}")
    print_check("OK" if ok else "FAIL", message)
    record("mcp", "OK" if ok else "FAIL", "arch-standard list_rules")
    structured["mcp"] = mcp_results

    print()
    print("== Gate Smoke Test ==")
    exit_code, output = run_capture(["python", "scripts/doctor_smoke.py"], cwd=root)
    if exit_code == 0:
        print_check("OK", "Gate smoke test passed.")
        record("gate_smoke", "OK", "passed")
    else:
        print_check("FAIL", f"Gate smoke test failed: {output}")
        record("gate_smoke", "FAIL", output)
    structured["gate_smoke"] = {"ok": exit_code == 0, "output": output}

    print()
    print("== Test Baseline ==")
    exit_code, output = run_capture(["python", "-m", "pytest", "--collect-only", "-q"], cwd=root)
    if exit_code != 0:
        print_check("FAIL", f"pytest collection failed: {output}")
        record("test_baseline", "FAIL", output)
    else:
        match = re.search(r"(\d+)\s+tests?\s+collected", output)
        if not match:
            print_check("WARN", "pytest collection finished, but the collected test count could not be parsed.")
            record("test_baseline", "WARN", "could not parse collected count")
        else:
            count = int(match.group(1))
            if count < 7:
                print_check("FAIL", f"pytest collected only {count} test(s); expected at least 7.")
                record("test_baseline", "FAIL", f"{count} collected")
            else:
                print_check("OK", f"pytest default collection baseline is healthy: {count} test(s) collected.")
                record("test_baseline", "OK", f"{count} collected")
    structured["test_baseline"] = {"ok": exit_code == 0 and "FAIL" not in [s["level"] for s in sections if s["section"] == "test_baseline"], "output": output}

    print()
    print("== PolyQuery ==")
    polyquery_example_ok, polyquery_example_message = path_required(root / "config/polyquery.example.json", "PolyQuery example config")
    print_check("OK" if polyquery_example_ok else "FAIL", polyquery_example_message)
    polyquery_local_ok, polyquery_local_message = test_json_file(root / "config/polyquery.json", "Local PolyQuery config")
    print_check("OK" if polyquery_local_ok else "WARN", polyquery_local_message)
    structured["polyquery"] = {"example_config": polyquery_example_ok, "local_config": polyquery_local_ok}
    record("polyquery", "OK", "checked")
    ok, message = run_polyquery_governance(root)
    print_check("OK" if ok else "FAIL", message)
    record("polyquery", "OK" if ok else "FAIL", message)

    print()
    print("== Attached Project ==")
    ok, message = validate_attachment_shape(root)
    print_check("OK" if ok else "WARN", message)
    record("attached_project", "OK" if ok else "WARN", message)
    structured["attached_project"] = {"ok": ok, "message": message}

    print()
    print("== Baseline ==")
    status, count = count_baseline_buckets(root)
    if status == "missing":
        print_check("WARN", "Baseline root is missing. Run refresh-baseline after onboarding.")
        record("baseline", "WARN", "missing")
    elif status == "empty":
        print_check("WARN", "Baseline root exists but contains no buckets.")
        record("baseline", "WARN", "empty")
    else:
        print_check("OK", f"Baseline buckets found: {count}")
        record("baseline", "OK", f"{count} buckets")
    structured["baseline"] = {"status": status, "count": count}
    ok, message = run_baseline_key_partition_governance(root)
    print_check("OK" if ok else "FAIL", message)
    record("baseline_keys", "OK" if ok else "FAIL", message)
    structured["baseline_keys"] = {"ok": ok, "message": message}

    print()
    print("== Security ==")
    security_warnings = find_security_warnings(root)
    if not security_warnings:
        print_check("OK", "No obvious plaintext credentials found in config/.spec/.env files.")
        record("security", "OK", "none")
    else:
        for warning in security_warnings:
            print_check("WARN", f"Potential plaintext secret: {warning}")
            record("security", "WARN", warning)
    structured["security"] = {"warnings": security_warnings}

    exit_code = 0
    if has_failure:
        print()
        print_check("FAIL", "Doctor finished with failures.")
        exit_code = 1
    elif strict and has_warning:
        print()
        print_check("FAIL", "Doctor finished with warnings; Strict mode treats warnings as failures.")
        exit_code = 1
    elif has_warning:
        print()
        print_check("WARN", "Doctor finished with warnings; local source integration is not blocked.")
    else:
        print()
        print_check("OK", "Doctor finished. This environment is ready for phase-1 agent integration.")

    return exit_code, sections, structured
