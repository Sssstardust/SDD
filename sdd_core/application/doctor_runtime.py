#!/usr/bin/env python3
"""
Application-layer doctor runtime orchestration (Declarative).
"""

from __future__ import annotations

from typing import Any, Callable

import json
import re
import shutil
from pathlib import Path

from sdd_core.infrastructure.doctor_checks import (
    count_baseline_buckets,
    find_security_warnings,
    path_required,
    run_capture,
    run_mcp_smoke,
    test_json_file,
    test_version,
    validate_attachment_shape,
)
from sdd_core.application.gates.gate_runtime import check_baseline_keys as check_baseline_keys_runtime


def attached_languages_include_java() -> bool:
    try:
        from sdd_core.domain.attached_project import load_attachment_config
        from sdd_core.domain.language_profiles import normalize_language
    except Exception:
        return True

    attachment = load_attachment_config()
    if not isinstance(attachment, dict):
        return True

    components = attachment.get("components")
    if not isinstance(components, list) or not components:
        return normalize_language(attachment.get("language")) == "java"

    for component in components:
        if not isinstance(component, dict):
            continue
        language = component.get("language")
        if language is None or normalize_language(language) == "java":
            return True
    return False


def run_baseline_key_partition_governance(root: Path) -> tuple[bool, str]:
    exit_code = check_baseline_keys_runtime()
    if exit_code == 0:
        return True, "baseline key partition validation passed"
    return False, "baseline key partition validation failed"


class DoctorEngine:
    def __init__(self, root: Path, strict: bool, print_check: Callable[[str, str], None]):
        self.root = root
        self.strict = strict
        self.print_check = print_check
        self.has_failure = False
        self.has_warning = False
        self.sections: list[dict[str, Any]] = []
        self.structured: dict[str, Any] = {}

    def record(self, section: str, level: str, message: str) -> None:
        self.sections.append({"section": section, "level": level, "message": message})
        if level == "FAIL":
            self.has_failure = True
        elif level == "WARN":
            self.has_warning = True

    def run_rule(self, category_id: str, rule: dict[str, Any]) -> None:
        rule_type = rule.get("type")
        description = rule.get("description", "Unknown Check")
        severity = rule.get("severity", "FAIL")

        condition = rule.get("condition")
        if condition == "needs_java" and not attached_languages_include_java():
            self.print_check("OK", f"{description} not required (attached project language is not Java).")
            return

        if rule_type == "command_version":
            command = rule.get("command", [])
            if command[0] == "javac" and not shutil.which("javac"):
                self.print_check("WARN", f"javac was not found; Gate 5 Java verification may be unavailable.")
                self.record(category_id, "WARN", "javac missing")
                return
            ok, message = test_version(
                description,
                command,
                int(rule.get("required_major", 0)),
                int(rule.get("required_minor", 0)),
            )
            level = "OK" if ok else severity
            self.print_check(level, message)
            self.record(category_id, level, description)
            self.structured.setdefault(category_id, {})[rule.get("id", description)] = ok

        elif rule_type == "path_exists":
            target_path = self.root / str(rule.get("path"))
            ok, message = path_required(target_path, description)
            level = "OK" if ok else severity
            self.print_check(level, message)
            self.record(category_id, level, description)
            self.structured.setdefault(category_id, []).append({"description": description, "ok": ok})

        elif rule_type == "mcp_smoke_test":
            target_path = self.root / str(rule.get("path"))
            # ensure path
            ok, message = path_required(target_path, description)
            if not ok:
                self.print_check(severity, message)
                self.record(category_id, severity, description)
                self.structured.setdefault(category_id, []).append({"description": description, "ok": False})
                return
            ok, message = run_mcp_smoke(self.root, target_path, str(rule.get("tool")), str(rule.get("arguments")))
            level = "OK" if ok else severity
            self.print_check(level, message)
            self.record(category_id, level, description)
            self.structured.setdefault(category_id, []).append({"description": description, "ok": ok})

        elif rule_type == "custom_pytest_baseline":
            exit_code, output = run_capture(["python", "-m", "pytest", "--collect-only", "-q"], cwd=self.root)
            if exit_code != 0:
                self.print_check("FAIL", f"pytest collection failed: {output}")
                self.record(category_id, "FAIL", output)
                self.structured[category_id] = {"ok": False, "output": output}
            else:
                match = re.search(r"(\d+)\s+tests?\s+collected", output)
                if not match:
                    self.print_check("WARN", "pytest collection finished, but the collected test count could not be parsed.")
                    self.record(category_id, "WARN", "could not parse collected count")
                    self.structured[category_id] = {"ok": True, "output": output}
                else:
                    count = int(match.group(1))
                    if count < 5:
                        self.print_check("FAIL", f"pytest collected only {count} test(s); expected at least 5.")
                        self.record(category_id, "FAIL", f"{count} collected")
                        self.structured[category_id] = {"ok": False, "output": output}
                    else:
                        self.print_check("OK", f"pytest default collection baseline is healthy: {count} test(s) collected.")
                        self.record(category_id, "OK", f"{count} collected")
                        self.structured[category_id] = {"ok": True, "output": output}

        elif rule_type == "custom_polyquery":
            ok, message = test_json_file(self.root / "config/polyquery.json", "Local PolyQuery config")
            level = "OK" if ok else "WARN"
            self.print_check(level, message)
            self.record(category_id, level, message)
            self.structured[category_id] = {"local_config": ok}

        elif rule_type == "custom_attached_project":
            ok, message = validate_attachment_shape(self.root)
            level = "OK" if ok else "WARN"
            self.print_check(level, message)
            self.record(category_id, level, message)
            self.structured[category_id] = {"ok": ok, "message": message}

        elif rule_type == "custom_baseline_governance":
            status, count = count_baseline_buckets(self.root)
            if status == "missing":
                self.print_check("WARN", "Baseline root is missing. Run refresh-baseline after onboarding.")
                self.record("baseline", "WARN", "missing")
            elif status == "empty":
                self.print_check("WARN", "Baseline root exists but contains no buckets.")
                self.record("baseline", "WARN", "empty")
            else:
                self.print_check("OK", f"Baseline buckets found: {count}")
                self.record("baseline", "OK", f"{count} buckets")
            self.structured["baseline"] = {"status": status, "count": count}
            
            ok, message = run_baseline_key_partition_governance(self.root)
            level = "OK" if ok else "FAIL"
            self.print_check(level, message)
            self.record("baseline_keys", level, message)
            self.structured["baseline_keys"] = {"ok": ok, "message": message}

        elif rule_type == "custom_security":
            warnings = find_security_warnings(self.root)
            if not warnings:
                self.print_check("OK", "No obvious plaintext credentials found in config/.spec/.env files.")
                self.record(category_id, "OK", "none")
            else:
                for warning in warnings:
                    self.print_check("WARN", f"Potential plaintext secret: {warning}")
                    self.record(category_id, "WARN", warning)
            self.structured[category_id] = {"warnings": warnings}


def run_doctor(
    *,
    root: Path,
    strict: bool,
    json_mode: bool,
    print_check: Callable[[str, str], None],
) -> tuple[int, list[dict[str, Any]], dict[str, Any]]:
    print("SDD Doctor")
    print(f"Repo: {root}\n")

    manifest_path = root / "sdd_core" / "config" / "doctor_manifest.json"
    if not manifest_path.exists():
        print_check("FAIL", f"Missing manifest: {manifest_path}")
        return 1, [], {}

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print_check("FAIL", f"Failed to load manifest: {exc}")
        return 1, [], {}

    engine = DoctorEngine(root, strict, print_check)

    for category in manifest.get("categories", []):
        cat_id = category.get("id", "unknown")
        print(f"== {category.get('name', cat_id)} ==")
        for rule in category.get("rules", []):
            engine.run_rule(cat_id, rule)
        print()

    exit_code = 0
    if engine.has_failure:
        print_check("FAIL", "Doctor finished with failures.")
        exit_code = 1
    elif strict and engine.has_warning:
        print_check("FAIL", "Doctor finished with warnings; Strict mode treats warnings as failures.")
        exit_code = 1
    elif engine.has_warning:
        print_check("WARN", "Doctor finished with warnings; local source integration is not blocked.")
    else:
        print_check("OK", "Doctor finished. This environment is ready for phase-1 agent integration.")

    return exit_code, engine.sections, engine.structured
