#!/usr/bin/env python3
"""
Cross-platform doctor entrypoint.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def run_capture(command: list[str], *, cwd: Path | None = None) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        return 1, str(exc)
    output = (result.stdout or "") + (("\n" + result.stderr) if result.stderr else "")
    return result.returncode, output.strip()


def print_check(level: str, message: str) -> None:
    print(f"[{level}] {message}")


def test_version(name: str, command: list[str], required_major: int, required_minor: int = 0) -> bool:
    if shutil.which(command[0]) is None:
        print_check("FAIL", f"{name} was not found. Please install it first.")
        return False
    exit_code, output = run_capture(command)
    if exit_code != 0 or not output:
        print_check("FAIL", f"{name} version check failed: {output}")
        return False
    match = re.search(r"(\d+)\.(\d+)", output)
    if not match:
        print_check("WARN", f"{name} is installed, but the version could not be parsed: {output}")
        return True
    major = int(match.group(1))
    minor = int(match.group(2))
    if major < required_major or (major == required_major and minor < required_minor):
        print_check("FAIL", f"{name} version is too old: {output}. Required >= {required_major}.{required_minor}.")
        return False
    print_check("OK", f"{name} is available: {output}")
    return True


def path_required(path: Path, description: str) -> bool:
    if path.exists():
        print_check("OK", f"{description} exists: {path}")
        return True
    print_check("FAIL", f"{description} is missing: {path}")
    return False


def test_json_file(path: Path, description: str) -> bool:
    if not path.exists():
        print_check("WARN", f"{description} is missing: {path}")
        return False
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print_check("WARN", f"{description} is not valid JSON: {exc}")
        return False
    print_check("OK", f"{description} is valid JSON: {path}")
    return True


def run_polyquery_governance(root: Path) -> tuple[bool, str]:
    script = root / "scripts" / "check_polyquery_config.py"
    if not script.exists():
        return False, f"polyquery governance script is missing: {script}"
    exit_code, output = run_capture(["python", str(script), "--config", str(root / "config" / "polyquery.example.json")], cwd=root)
    if exit_code == 0:
        return True, output or "polyquery governance passed"
    return False, output or "polyquery governance failed"


def find_security_warnings(root: Path) -> list[str]:
    patterns = [
        r"password\s*[:=]\s*['\"]?[^'\"\s`$][^'\"\s,}]+",
        r"jdbc:[^\r\n]+",
        r"(mysql|postgres|postgresql|oracle)://[^\r\n]+:[^\r\n@`$]+@",
        r"AKIA[0-9A-Z]{16}",
        r"secret[_-]?key\s*[:=]\s*['\"]?[^'\"\s]+",
    ]
    roots = [root / "config", root / ".spec"]
    files: list[Path] = []
    for candidate in roots:
        if candidate.exists():
            files.extend(
                path
                for path in candidate.rglob("*")
                if path.is_file() and path.suffix.lower() in {".json", ".yaml", ".yml", ".env", ".txt", ".md"}
            )
    files.extend(path for path in root.glob(".env*") if path.is_file() and path.name != ".env.example")

    warnings: list[str] = []
    for file in files:
        try:
            text = file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if not text.strip():
            continue
        for pattern in patterns:
            if re.search(pattern, text):
                warnings.append(f"{file.relative_to(root)} matches {pattern}")
                break
    return warnings


def emit_json_result(status: str, sections: list[dict[str, object]]) -> None:
    print(json.dumps({"status": status, "sections": sections}, ensure_ascii=False))


def count_baseline_buckets(root: Path) -> tuple[str, int]:
    baseline_root = root / ".spec" / "baselines"
    if not baseline_root.exists():
        return "missing", 0
    buckets = [path for path in baseline_root.iterdir() if path.is_dir()]
    return ("ok" if buckets else "empty"), len(buckets)


def validate_attachment_shape(root: Path) -> tuple[bool, str]:
    attachment_path = root / ".spec" / "attached-project.json"
    if not attachment_path.exists():
        return False, f"attached project config is missing: {attachment_path}"
    try:
        payload = json.loads(attachment_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"attached project config is invalid JSON: {exc}"
    if not isinstance(payload, dict):
        return False, "attached project config is not an object"
    if not payload.get("project_root") and not payload.get("design_roots"):
        return False, "attached project config is missing project_root/design_roots"
    return True, "Attached project config is readable."


def run_mcp_smoke(root: Path, server_path: Path, tool: str, arguments_json: str) -> tuple[bool, str]:
    if not server_path.exists():
        return False, f"MCP entrypoint does not exist: {server_path}"
    if shutil.which("node") is None:
        return False, "MCP requires Node.js."
    exit_code, output = run_capture(["node", str(server_path), "--tool", tool, "--arguments", arguments_json], cwd=root)
    if exit_code == 0:
        return True, f"MCP smoke test passed: {tool}"
    return False, f"MCP smoke test failed: {output}"


def run_baseline_key_partition_governance(root: Path) -> tuple[bool, str]:
    script = root / "scripts" / "check_baseline_key_partition.py"
    if not script.exists():
        return False, f"baseline key partition script is missing: {script}"
    exit_code, output = run_capture(["python", str(script)], cwd=root)
    if exit_code == 0:
        return True, output or "baseline key partition validation passed"
    return False, output or "baseline key partition validation failed"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    parser.add_argument("--json", action="store_true", help="Emit structured JSON output instead of human-readable text.")
    args = parser.parse_args(argv)

    has_failure = False
    has_warning = False
    sections: list[dict[str, object]] = []
    structured: dict[str, object] = {}

    def mark(level: str) -> None:
        nonlocal has_failure, has_warning
        if level == "FAIL":
            has_failure = True
        elif level == "WARN":
            has_warning = True

    def record(section: str, level: str, message: str) -> None:
        nonlocal has_failure, has_warning
        sections.append({"section": section, "level": level, "message": message})
        if level == "FAIL":
            has_failure = True
        elif level == "WARN":
            has_warning = True

    print("SDD Doctor")
    print(f"Repo: {ROOT}")
    print()

    print("== Toolchain ==")
    ok = test_version("Python", ["python", "--version"], 3, 13)
    record("toolchain", "OK" if ok else "FAIL", "Python")
    ok = test_version("Node.js", ["node", "--version"], 18, 0)
    record("toolchain", "OK" if ok else "FAIL", "Node.js")
    structured["toolchain"] = {
        "python": ok,
        "node": ok,
    }
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
        path_ok = path_required(ROOT / rel, description)
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
        path_ok = path_required(ROOT / rel, description)
        mcp_results.append({"description": description, "ok": path_ok})
        if not path_ok:
            record("mcp", "FAIL", description)
    ok, message = run_mcp_smoke(ROOT, ROOT / "mcp-servers/project-explorer/dist/server.js", "scan_modules", '{"keywords":["payment"],"limit":1,"force_refresh":false}')
    print_check("OK" if ok else "FAIL", message)
    record("mcp", "OK" if ok else "FAIL", "project-explorer scan_modules")
    ok, message = run_mcp_smoke(ROOT, ROOT / "mcp-servers/arch-standard/dist/server.js", "list_rules", "{}")
    print_check("OK" if ok else "FAIL", message)
    record("mcp", "OK" if ok else "FAIL", "arch-standard list_rules")
    structured["mcp"] = mcp_results

    print()
    print("== Gate Smoke Test ==")
    exit_code, output = run_capture(["python", "scripts/doctor_smoke.py"], cwd=ROOT)
    if exit_code == 0:
        print_check("OK", "Gate smoke test passed.")
        record("gate_smoke", "OK", "passed")
    else:
        print_check("FAIL", f"Gate smoke test failed: {output}")
        record("gate_smoke", "FAIL", output)
    structured["gate_smoke"] = {"ok": exit_code == 0, "output": output}

    print()
    print("== Test Baseline ==")
    exit_code, output = run_capture(["python", "-m", "pytest", "--collect-only", "-q"], cwd=ROOT)
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
    polyquery_example_ok = path_required(ROOT / "config/polyquery.example.json", "PolyQuery example config")
    polyquery_local_ok = test_json_file(ROOT / "config/polyquery.json", "Local PolyQuery config")
    structured["polyquery"] = {
        "example_config": polyquery_example_ok,
        "local_config": polyquery_local_ok,
    }
    record("polyquery", "OK", "checked")
    ok, message = run_polyquery_governance(ROOT)
    print_check("OK" if ok else "FAIL", message)
    record("polyquery", "OK" if ok else "FAIL", message)

    print()
    print("== Attached Project ==")
    ok, message = validate_attachment_shape(ROOT)
    print_check("OK" if ok else "WARN", message)
    record("attached_project", "OK" if ok else "WARN", message)
    structured["attached_project"] = {"ok": ok, "message": message}

    print()
    print("== Baseline ==")
    status, count = count_baseline_buckets(ROOT)
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
    ok, message = run_baseline_key_partition_governance(ROOT)
    print_check("OK" if ok else "FAIL", message)
    record("baseline_keys", "OK" if ok else "FAIL", message)
    structured["baseline_keys"] = {"ok": ok, "message": message}

    print()
    print("== Security ==")
    security_warnings = find_security_warnings(ROOT)
    if not security_warnings:
        print_check("OK", "No obvious plaintext credentials found in config/.spec/.env files.")
        record("security", "OK", "none")
    else:
        for warning in security_warnings:
            print_check("WARN", f"Potential plaintext secret: {warning}")
            record("security", "WARN", warning)
    structured["security"] = {"warnings": security_warnings}

    print()
    if has_failure:
        print_check("FAIL", "Doctor finished with failures.")
        if args.json:
            emit_json_result("FAIL", [*sections, {"section": "structured", "level": "INFO", "message": json.dumps(structured, ensure_ascii=False)}])
        return 1
    if args.strict and has_warning:
        print_check("FAIL", "Doctor finished with warnings; Strict mode treats warnings as failures.")
        if args.json:
            emit_json_result("FAIL", [*sections, {"section": "structured", "level": "INFO", "message": json.dumps(structured, ensure_ascii=False)}])
        return 1
    if has_warning:
        print_check("WARN", "Doctor finished with warnings; local source integration is not blocked.")
        if args.json:
            emit_json_result("WARN", [*sections, {"section": "structured", "level": "INFO", "message": json.dumps(structured, ensure_ascii=False)}])
        return 0
    print_check("OK", "Doctor finished. This environment is ready for phase-1 agent integration.")
    if args.json:
        emit_json_result("OK", [*sections, {"section": "structured", "level": "INFO", "message": json.dumps(structured, ensure_ascii=False)}])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
