#!/usr/bin/env python3
"""
Infrastructure checks extracted from doctor.py.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path


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


def test_version(name: str, command: list[str], required_major: int, required_minor: int = 0) -> tuple[bool, str]:
    if shutil.which(command[0]) is None:
        return False, f"{name} was not found. Please install it first."
    exit_code, output = run_capture(command)
    if exit_code != 0 or not output:
        return False, f"{name} version check failed: {output}"
    match = re.search(r"(\d+)\.(\d+)", output)
    if not match:
        return True, f"{name} is installed, but the version could not be parsed: {output}"
    major = int(match.group(1))
    minor = int(match.group(2))
    if major < required_major or (major == required_major and minor < required_minor):
        return False, f"{name} version is too old: {output}. Required >= {required_major}.{required_minor}."
    return True, f"{name} is available: {output}"


def path_required(path: Path, description: str) -> tuple[bool, str]:
    if path.exists():
        return True, f"{description} exists: {path}"
    return False, f"{description} is missing: {path}"


def test_json_file(path: Path, description: str) -> tuple[bool, str]:
    if not path.exists():
        return False, f"{description} is missing: {path}"
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"{description} is not valid JSON: {exc}"
    return True, f"{description} is valid JSON: {path}"


def run_mcp_smoke(root: Path, server_path: Path, tool: str, arguments_json: str) -> tuple[bool, str]:
    if not server_path.exists():
        return False, f"MCP entrypoint does not exist: {server_path}"
    if shutil.which("node") is None:
        return False, "MCP requires Node.js."
    exit_code, output = run_capture(["node", str(server_path), "--tool", tool, "--arguments", arguments_json], cwd=root)
    if exit_code == 0:
        return True, f"MCP smoke test passed: {tool}"
    return False, f"MCP smoke test failed: {output}"


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


def count_baseline_buckets(root: Path) -> tuple[str, int]:
    baseline_root = root / ".spec" / "baselines"
    if not baseline_root.exists():
        return "missing", 0
    buckets = [path for path in baseline_root.iterdir() if path.is_dir()]
    return ("ok" if buckets else "empty"), len(buckets)


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
