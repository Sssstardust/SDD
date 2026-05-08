#!/usr/bin/env python3
"""
check_design_test_coverage.py

读取 reports/v{N}/gate4-skeleton.json 和测试骨架文件，
检查 TODO[REQ-xxx] 是否已消除，并输出 verify-report.json。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from attached_project import DEFAULT_ATTACHMENT_PATH, load_attachment_config, resolve_module_map_scan_settings, source_signature
from baseline_extractors import build_design_resource_claims_for_pack, extract_mermaid_participants, summarize_resource_claims
from baseline_paths import get_active_baseline_dir
from concurrency import atomic_write_text, feature_lock
from design_evidence import evidence_level_for_schema_context, hash_file, resolve_design_pack_dir
from feature_brief import extract_affected_components, extract_risk_tier
from gate_report import write_gate_section
from refresh_schema_context import resolve_schema_context_sources, source_signature as schema_context_source_signature
from versioning import detect_latest_design_path, reports_dir_for_design, resolve_feature_dir


ROOT = Path(__file__).resolve().parent.parent
M2_REPO = Path.home() / ".m2" / "repository"


def trim_output(text: str, limit: int = 1000) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def normalize_attached_command(
    raw_command: object,
    feature_name: str,
    *,
    component_id: str = "",
    design_version: str = "",
) -> list[str] | None:
    values = {
        "feature_name": feature_name,
        "component_id": component_id,
        "design_version": design_version,
    }
    if isinstance(raw_command, str):
        return [part.format(**values) for part in raw_command.split() if part]
    if isinstance(raw_command, list) and all(isinstance(item, str) for item in raw_command):
        return [str(item).format(**values) for item in raw_command]
    return None


def collect_attached_verification_specs(
    attachment: dict[str, object],
    *,
    affected_components: set[str] | None = None,
) -> list[dict[str, object]]:
    project_root_value = attachment.get("project_root")
    project_root = Path(str(project_root_value)).resolve() if isinstance(project_root_value, str) else ROOT
    components = attachment.get("components") if isinstance(attachment.get("components"), list) else []
    component_index: dict[str, dict[str, object]] = {}
    for component in components:
        if isinstance(component, dict) and isinstance(component.get("component_id"), str) and component.get("component_id"):
            component_index[str(component["component_id"])] = component

    specs: list[dict[str, object]] = []
    raw_commands = attachment.get("verification_commands") or attachment.get("test_commands")
    if isinstance(raw_commands, list):
        for index, item in enumerate(raw_commands, start=1):
            if isinstance(item, dict):
                component_id = str(item.get("component_id") or "")
                if affected_components and component_id and component_id not in affected_components:
                    continue
                component = component_index.get(component_id) if component_id else None
                cwd_value = item.get("cwd")
                cwd = (
                    Path(str(cwd_value)).resolve()
                    if isinstance(cwd_value, str)
                    else Path(str(component.get("project_root"))).resolve()
                    if isinstance(component, dict) and isinstance(component.get("project_root"), str)
                    else project_root
                )
                specs.append(
                    {
                        "name": str(item.get("name") or f"verification-{index}"),
                        "component_id": component_id,
                        "command": item.get("command"),
                        "cwd": cwd,
                    }
                )
            else:
                specs.append({"name": f"verification-{index}", "component_id": "", "command": item, "cwd": project_root})

    for component in components:
        if not isinstance(component, dict):
            continue
        component_commands = component.get("verification_commands") or component.get("test_commands")
        if not isinstance(component_commands, list) or not component_commands:
            continue
        component_id = str(component.get("component_id") or "")
        if affected_components and component_id and component_id not in affected_components:
            continue
        default_cwd = Path(str(component.get("project_root"))).resolve() if isinstance(component.get("project_root"), str) else project_root
        for index, item in enumerate(component_commands, start=1):
            if isinstance(item, dict):
                cwd_value = item.get("cwd")
                cwd = Path(str(cwd_value)).resolve() if isinstance(cwd_value, str) else default_cwd
                specs.append(
                    {
                        "name": str(item.get("name") or f"{component_id or 'component'}-verification-{index}"),
                        "component_id": str(item.get("component_id") or component_id),
                        "command": item.get("command"),
                        "cwd": cwd,
                    }
                )
            else:
                specs.append(
                    {
                        "name": f"{component_id or 'component'}-verification-{index}",
                        "component_id": component_id,
                        "command": item,
                        "cwd": default_cwd,
                    }
                )
    return specs


def run_attached_verification_commands(
    feature_name: str,
    *,
    attachment_path: Path = DEFAULT_ATTACHMENT_PATH,
    require_configured: bool = False,
    design_version: str = "",
    affected_components: list[str] | None = None,
) -> dict[str, object]:
    attachment = load_attachment_config(attachment_path)
    if not attachment:
        if require_configured:
            return {"status": "FAIL", "reason": "attached verification required but attached project is not configured", "commands": []}
        return {"status": "SKIPPED", "reason": "未配置 attached project", "commands": []}

    command_specs = collect_attached_verification_specs(
        attachment,
        affected_components={item for item in (affected_components or []) if item} or None,
    )
    if not command_specs:
        if require_configured:
            return {"status": "FAIL", "reason": "attached verification required but verification_commands is not configured", "commands": []}
        return {"status": "SKIPPED", "reason": "未配置 verification_commands", "commands": []}

    results: list[dict[str, object]] = []
    component_statuses: dict[str, list[str]] = {}

    for spec in command_specs:
        name = str(spec.get("name") or "verification")
        component_id = str(spec.get("component_id") or "")
        command = normalize_attached_command(
            spec.get("command"),
            feature_name,
            component_id=component_id,
            design_version=design_version,
        )
        cwd_value = spec.get("cwd")
        cwd = cwd_value if isinstance(cwd_value, Path) else ROOT

        if not command:
            results.append({"name": name, "status": "FAIL", "reason": "verification command is empty or invalid"})
            if component_id:
                component_statuses.setdefault(component_id, []).append("FAIL")
            continue

        run_result = subprocess.run(
            command,
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
        )
        results.append(
            {
                "name": name,
                "component_id": component_id,
                "status": "PASS" if run_result.returncode == 0 else "FAIL",
                "command": command,
                "cwd": str(cwd),
                "returncode": run_result.returncode,
                "stdout_tail": trim_output(run_result.stdout),
                "stderr_tail": trim_output(run_result.stderr),
            }
        )
        if component_id:
            component_statuses.setdefault(component_id, []).append("PASS" if run_result.returncode == 0 else "FAIL")

    status = "PASS" if all(result.get("status") == "PASS" for result in results) else "FAIL"
    return {
        "status": status,
        "commands": results,
        "components": [
            {
                "component_id": component_id,
                "status": "PASS" if all(item == "PASS" for item in statuses) else "FAIL",
                "command_count": len(statuses),
            }
            for component_id, statuses in sorted(component_statuses.items())
        ],
    }


def collect_attached_test_scan_targets(
    attachment: dict[str, object],
    *,
    affected_components: set[str] | None = None,
) -> list[dict[str, object]]:
    components = attachment.get("components") if isinstance(attachment.get("components"), list) else []
    targets: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()

    for component in components:
        if not isinstance(component, dict):
            continue
        component_id = str(component.get("component_id") or "")
        if affected_components and component_id and component_id not in affected_components:
            continue
        roots: list[Path] = []
        project_root_value = component.get("project_root")
        if isinstance(project_root_value, str) and project_root_value:
            roots.append(Path(project_root_value).resolve())
        else:
            scan_roots = component.get("scan_roots")
            if isinstance(scan_roots, list):
                roots.extend(Path(str(item)).resolve() for item in scan_roots if isinstance(item, str) and item)
        for root in roots:
            key = (component_id, str(root))
            if key in seen:
                continue
            seen.add(key)
            targets.append({"component_id": component_id, "root": root})

    if targets:
        return targets

    roots: list[Path] = []
    project_root_value = attachment.get("project_root")
    if isinstance(project_root_value, str) and project_root_value:
        roots.append(Path(project_root_value).resolve())
    else:
        scan_roots = attachment.get("scan_roots")
        if isinstance(scan_roots, list):
            roots.extend(Path(str(item)).resolve() for item in scan_roots if isinstance(item, str) and item)

    for root in roots:
        key = ("", str(root))
        if key in seen:
            continue
        seen.add(key)
        targets.append({"component_id": "", "root": root})
    return targets


def is_probable_real_test_source(path: Path) -> bool:
    name = path.name.lower()
    suffix = path.suffix.lower()
    normalized = str(path).replace("\\", "/").lower()
    if suffix == ".java":
        return "/src/test/java/" in normalized or name.endswith("test.java") or name.endswith("tests.java")
    if suffix == ".py":
        return "/tests/" in normalized or name.startswith("test_") or name.endswith("_test.py")
    return False


def iter_real_test_source_files(root: Path) -> list[Path]:
    if not root.exists():
        return []

    skipped_dirs = {
        ".git",
        ".hg",
        ".idea",
        ".mypy_cache",
        ".pytest_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "out",
        "target",
    }
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [item for item in dirnames if item not in skipped_dirs]
        base = Path(dirpath)
        for filename in filenames:
            candidate = base / filename
            if is_probable_real_test_source(candidate):
                files.append(candidate.resolve())
    return sorted(set(files))


def extract_req_ids_from_real_test_source(content: str) -> list[str]:
    req_ids: set[str] = set()
    explicit_patterns = [
        r"@SddRequirement\(\s*[\"'](REQ-\d+)[\"']\s*\)",
        r"@DisplayName\(\s*[\"'][^\"']*(REQ-\d+)[^\"']*[\"']\s*\)",
        r"@pytest\.mark\.[A-Za-z_][A-Za-z0-9_]*\(\s*[\"'](REQ-\d+)[\"']\s*\)",
    ]
    for pattern in explicit_patterns:
        req_ids.update(re.findall(pattern, content))

    for line in content.splitlines():
        if "TODO[" in line:
            continue
        req_ids.update(re.findall(r"\bREQ-\d+\b", line))
    return sorted(req_ids)


def analyze_real_test_req_coverage(
    expected_req_ids: list[str],
    *,
    attachment_path: Path = DEFAULT_ATTACHMENT_PATH,
    affected_components: list[str] | None = None,
) -> dict[str, object]:
    expected = sorted({item for item in expected_req_ids if item})
    if not expected:
        return {
            "result": "PASS",
            "expected_req_ids": [],
            "covered_req_ids": [],
            "missing_req_ids": [],
            "matched_file_count": 0,
            "matched_files": [],
            "details": [],
            "reason": "no expected req ids",
        }

    attachment = load_attachment_config(attachment_path)
    if not attachment:
        return {
            "result": "SKIPPED",
            "expected_req_ids": expected,
            "covered_req_ids": [],
            "missing_req_ids": expected,
            "matched_file_count": 0,
            "matched_files": [],
            "details": [{"req_id": req_id, "covered": False, "matched_files": []} for req_id in expected],
            "reason": "attached project is not configured",
        }

    targets = collect_attached_test_scan_targets(
        attachment,
        affected_components={item for item in (affected_components or []) if item} or None,
    )
    if not targets:
        return {
            "result": "SKIPPED",
            "expected_req_ids": expected,
            "covered_req_ids": [],
            "missing_req_ids": expected,
            "matched_file_count": 0,
            "matched_files": [],
            "details": [{"req_id": req_id, "covered": False, "matched_files": []} for req_id in expected],
            "reason": "no attached test scan targets",
        }

    expected_set = set(expected)
    matched_files: list[dict[str, object]] = []
    req_to_files: dict[str, list[str]] = {req_id: [] for req_id in expected}

    for target in targets:
        component_id = str(target.get("component_id") or "")
        root = target.get("root")
        if not isinstance(root, Path):
            continue
        for test_file in iter_real_test_source_files(root):
            try:
                content = test_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            matched_req_ids = [req_id for req_id in extract_req_ids_from_real_test_source(content) if req_id in expected_set]
            if not matched_req_ids:
                continue
            file_record = {
                "component_id": component_id,
                "path": str(test_file),
                "req_ids": sorted(set(matched_req_ids)),
            }
            matched_files.append(file_record)
            for req_id in file_record["req_ids"]:
                req_to_files.setdefault(req_id, []).append(str(test_file))

    covered_req_ids = sorted(req_id for req_id, paths in req_to_files.items() if paths)
    missing_req_ids = sorted(req_id for req_id in expected if req_id not in covered_req_ids)
    details = [
        {
            "req_id": req_id,
            "covered": req_id in covered_req_ids,
            "matched_files": sorted(set(req_to_files.get(req_id, []))),
        }
        for req_id in expected
    ]
    return {
        "result": "PASS" if not missing_req_ids else "WARN",
        "expected_req_ids": expected,
        "covered_req_ids": covered_req_ids,
        "missing_req_ids": missing_req_ids,
        "matched_file_count": len(matched_files),
        "matched_files": matched_files,
        "details": details,
        "reason": "scanned attached real test sources",
    }


def extract_referenced_classes(design_text: str) -> list[str]:
    return extract_mermaid_participants(design_text)


def extract_referenced_method_calls(design_text: str) -> list[dict[str, object]]:
    alias_to_class: dict[str, str] = {}
    calls: list[dict[str, object]] = []
    in_sequence = False
    for raw_line in design_text.splitlines():
        line = raw_line.strip()
        if line.startswith("```mermaid"):
            in_sequence = False
            continue
        if line == "sequenceDiagram":
            in_sequence = True
            continue
        if line.startswith("```"):
            in_sequence = False
            continue
        if not in_sequence:
            continue

        participant = re.match(r"participant\s+([A-Za-z_][A-Za-z0-9_]*)\s+as\s+([A-Z][A-Za-z0-9_]*)", line)
        if participant:
            alias_to_class[participant.group(1)] = participant.group(2)
            continue
        bare_participant = re.match(r"participant\s+([A-Z][A-Za-z0-9_]*)\s*$", line)
        if bare_participant:
            alias_to_class[bare_participant.group(1)] = bare_participant.group(1)
            continue

        call = re.match(r"[A-Za-z_][A-Za-z0-9_]*\s*-+>>?\+?\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)\s*$", line)
        if not call:
            continue
        target_alias, method_name, args_text = call.groups()
        target_class = alias_to_class.get(target_alias, target_alias)
        if target_class and method_name:
            parameter_types = extract_design_parameter_type_hints(args_text)
            calls.append(
                {
                    "class_name": target_class,
                    "method_name": method_name,
                    "signature": f"{method_name}({args_text.strip()})",
                    "parameter_count": len(split_top_level_args(args_text)),
                    "parameter_types": parameter_types,
                }
            )
    deduped = {
        f"{item['class_name']}.{item['method_name']}::{','.join(item.get('parameter_types', []))}::{item.get('parameter_count', 0)}": item
        for item in calls
    }
    return [deduped[key] for key in sorted(deduped)]


def split_top_level_args(value: str) -> list[str]:
    if not value.strip():
        return []
    parts: list[str] = []
    current: list[str] = []
    angle_depth = 0
    paren_depth = 0
    bracket_depth = 0
    brace_depth = 0
    for char in value:
        if char == "<":
            angle_depth += 1
        elif char == ">":
            angle_depth = max(0, angle_depth - 1)
        elif char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth = max(0, paren_depth - 1)
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth = max(0, bracket_depth - 1)
        elif char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth = max(0, brace_depth - 1)
        elif char == "," and angle_depth == 0 and paren_depth == 0 and bracket_depth == 0 and brace_depth == 0:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
            continue
        current.append(char)
    part = "".join(current).strip()
    if part:
        parts.append(part)
    return parts


def normalize_type_name(value: object) -> str:
    if not isinstance(value, str):
        return ""
    normalized = re.sub(r"@\w+(?:\([^)]*\))?\s*", "", value).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = normalized.replace("? extends ", "").replace("? super ", "").replace("...", "[]")
    normalized = re.sub(r"\b(?:final|volatile|transient)\b\s*", "", normalized)
    normalized = re.sub(r"([A-Za-z_][A-Za-z0-9_$.]*)", lambda match: match.group(1).split(".")[-1], normalized)
    normalized = re.sub(r"\s*<\s*", "<", normalized)
    normalized = re.sub(r"\s*>\s*", ">", normalized)
    normalized = re.sub(r"\s*,\s*", ", ", normalized)
    normalized = re.sub(r"\s*\[\s*\]\s*", "[]", normalized)
    return normalized.strip()


def extract_design_parameter_type_hints(args_text: str) -> list[str]:
    hints: list[str] = []
    for item in split_top_level_args(args_text):
        candidate = item.strip()
        if not candidate:
            continue
        if " " not in candidate:
            continue
        tokens = candidate.split()
        type_candidate = " ".join(tokens[:-1]).strip()
        if not type_candidate:
            continue
        normalized = normalize_type_name(type_candidate)
        if normalized:
            hints.append(normalized)
    return hints


def method_name_from_signature(signature: object) -> str | None:
    if not isinstance(signature, str) or not signature:
        return None
    match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(", signature)
    return match.group(1) if match else None


def parameter_types_from_signature(signature: object) -> list[str]:
    if not isinstance(signature, str) or "(" not in signature or ")" not in signature:
        return []
    match = re.match(r"\s*[A-Za-z_][A-Za-z0-9_]*\s*\((.*)\)\s*", signature)
    if not match:
        return []
    params_text = match.group(1).strip()
    if not params_text:
        return []
    result: list[str] = []
    for item in split_top_level_args(params_text):
        candidate = item.strip()
        if not candidate:
            continue
        tokens = candidate.split()
        type_candidate = " ".join(tokens[:-1]).strip() if len(tokens) > 1 else candidate
        normalized = normalize_type_name(type_candidate)
        if normalized:
            result.append(normalized)
    return result


def build_method_detail_index(entry: dict[str, object]) -> list[dict[str, object]]:
    details = entry.get("method_details")
    indexed: list[dict[str, object]] = []
    if isinstance(details, list):
        for item in details:
            if not isinstance(item, dict):
                continue
            signature = item.get("signature")
            name = item.get("name") or method_name_from_signature(signature)
            parameter_types = item.get("parameter_types") if isinstance(item.get("parameter_types"), list) else []
            indexed.append(
                {
                    "name": str(name or ""),
                    "signature": str(signature or ""),
                    "parameter_types": [normalize_type_name(param) for param in parameter_types if isinstance(param, str)],
                }
            )
    if indexed:
        return indexed
    for signature in entry.get("public_methods", []):
        if not isinstance(signature, str):
            continue
        indexed.append(
            {
                "name": str(method_name_from_signature(signature) or ""),
                "signature": signature,
                "parameter_types": parameter_types_from_signature(signature),
            }
        )
    return indexed


def match_method_call(call: dict[str, object], entry: dict[str, object]) -> dict[str, object]:
    method_name = str(call.get("method_name") or "")
    expected_parameter_types = [normalize_type_name(item) for item in call.get("parameter_types", []) if isinstance(item, str)]
    expected_parameter_count = int(call.get("parameter_count") or 0)
    candidates = [item for item in build_method_detail_index(entry) if item.get("name") == method_name]
    if not candidates:
        return {
            "matched": False,
            "match_mode": "missing",
            "expected_signature": str(call.get("signature") or method_name),
            "matched_signature": None,
            "candidate_signatures": [],
        }
    if expected_parameter_types:
        for candidate in candidates:
            if candidate.get("parameter_types") == expected_parameter_types:
                return {
                    "matched": True,
                    "match_mode": "signature",
                    "expected_signature": str(call.get("signature") or method_name),
                    "matched_signature": candidate.get("signature"),
                    "candidate_signatures": [item.get("signature") for item in candidates if item.get("signature")],
                }
        return {
            "matched": False,
            "match_mode": "signature",
            "expected_signature": str(call.get("signature") or method_name),
            "matched_signature": None,
            "candidate_signatures": [item.get("signature") for item in candidates if item.get("signature")],
        }
    if expected_parameter_count:
        for candidate in candidates:
            if len(candidate.get("parameter_types", [])) == expected_parameter_count:
                return {
                    "matched": True,
                    "match_mode": "arity",
                    "expected_signature": str(call.get("signature") or method_name),
                    "matched_signature": candidate.get("signature"),
                    "candidate_signatures": [item.get("signature") for item in candidates if item.get("signature")],
                }
        return {
            "matched": False,
            "match_mode": "arity",
            "expected_signature": str(call.get("signature") or method_name),
            "matched_signature": None,
            "candidate_signatures": [item.get("signature") for item in candidates if item.get("signature")],
        }
    return {
        "matched": True,
        "match_mode": "name",
        "expected_signature": str(call.get("signature") or method_name),
        "matched_signature": candidates[0].get("signature"),
        "candidate_signatures": [item.get("signature") for item in candidates if item.get("signature")],
    }


def merge_module_entry(existing: dict[str, object], node: dict[str, object]) -> dict[str, object]:
    merged = dict(existing)
    for field in ("public_methods", "declared_public_methods", "inherited_public_methods", "fields", "annotations", "sources"):
        merged[field] = sorted(set(merged.get(field, [])) | set(node.get(field, [])))
    method_details = {
        json.dumps(item, sort_keys=True, ensure_ascii=False): item
        for item in merged.get("method_details", [])
        if isinstance(item, dict)
    }
    for item in node.get("method_details", []):
        if isinstance(item, dict):
            method_details[json.dumps(item, sort_keys=True, ensure_ascii=False)] = item
    if method_details:
        merged["method_details"] = [method_details[key] for key in sorted(method_details)]
    resource_keys = set(merged.get("resource_keys", []))
    if isinstance(merged.get("resource_key"), str):
        resource_keys.add(str(merged["resource_key"]))
    if isinstance(node.get("resource_key"), str):
        resource_keys.add(str(node["resource_key"]))
    merged["resource_keys"] = sorted(resource_keys)
    if not merged.get("fqn") and node.get("fqn"):
        merged["fqn"] = node.get("fqn")
    if not merged.get("source_kind") and node.get("source_kind"):
        merged["source_kind"] = node.get("source_kind")
    if not merged.get("component_id") and node.get("component_id"):
        merged["component_id"] = node.get("component_id")
    return merged


def build_module_entry_aliases(node: dict[str, object]) -> list[str]:
    aliases: list[str] = []
    for key in ("resource_key", "fqn", "simple_name", "class_name", "display_name", "name"):
        value = node.get(key)
        if not isinstance(value, str) or not value:
            continue
        aliases.append(value)
        aliases.append(value.split(".")[-1])
        if "::" in value:
            aliases.append(value.split("::")[-1])
            aliases.append(value.split("::")[-1].split(".")[-1])
    deduped: list[str] = []
    seen: set[str] = set()
    for item in aliases:
        if item and item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def extract_module_class_entries(
    module_map_path: Path,
    *,
    affected_components: list[str] | None = None,
) -> dict[str, list[dict[str, object]]]:
    if not module_map_path.exists():
        return {}

    data = json.loads(module_map_path.read_text(encoding="utf-8"))
    entries: dict[str, list[dict[str, object]]] = {}
    canonical_entries: dict[str, dict[str, object]] = {}
    affected_component_set = {item for item in (affected_components or []) if item}

    def collect(node: object) -> None:
        if isinstance(node, dict):
            class_name = node.get("class_name") or node.get("simple_name") or node.get("name")
            if isinstance(class_name, str):
                component_id = node.get("component_id")
                if affected_component_set and isinstance(component_id, str) and component_id and component_id not in affected_component_set:
                    pass
                else:
                    canonical_key = str(node.get("resource_key") or node.get("fqn") or class_name)
                    existing = canonical_entries.get(canonical_key)
                    canonical = merge_module_entry(existing, dict(node)) if isinstance(existing, dict) else dict(node)
                    canonical_entries[canonical_key] = canonical
            for value in node.values():
                collect(value)
        elif isinstance(node, list):
            for item in node:
                collect(item)

    collect(data)
    for canonical in canonical_entries.values():
        for alias in build_module_entry_aliases(canonical):
            entries.setdefault(alias, []).append(canonical)
    return entries


def resolve_module_class_entry(entries: dict[str, list[dict[str, object]]], class_name: str) -> dict[str, object] | None:
    candidates = entries.get(class_name) or entries.get(class_name.split(".")[-1]) or []
    if not candidates:
        return None
    java_candidates = [item for item in candidates if str(item.get("source_kind") or "").startswith("java")]
    if len(java_candidates) == 1:
        return java_candidates[0]
    exact_fqn = [item for item in candidates if str(item.get("fqn") or "") == class_name]
    if len(exact_fqn) == 1:
        return exact_fqn[0]
    if len(candidates) == 1:
        return candidates[0]
    return None


def module_class_candidates(entries: dict[str, list[dict[str, object]]], class_name: str) -> list[dict[str, object]]:
    return entries.get(class_name) or entries.get(class_name.split(".")[-1]) or []


def read_module_map_quality(module_map_path: Path) -> dict[str, object]:
    if not module_map_path.exists():
        return {"confidence": "missing", "unsupported_features": []}
    try:
        data = json.loads(module_map_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"confidence": "invalid", "unsupported_features": []}
    if not isinstance(data, dict):
        return {"confidence": "invalid", "unsupported_features": []}
    unsupported_features = data.get("unsupported_features")
    if not isinstance(unsupported_features, list):
        unsupported_features = []
    return {
        "scanner": data.get("scanner"),
        "confidence": data.get("confidence"),
        "unsupported_features": unsupported_features,
        "scan_quality": data.get("scan_quality") if isinstance(data.get("scan_quality"), dict) else {},
    }


def parse_ttl(value: object) -> timedelta | None:
    if isinstance(value, (int, float)):
        return timedelta(seconds=float(value))
    if not isinstance(value, str) or not value:
        return None
    if value.isdigit():
        return timedelta(seconds=int(value))
    match = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", value)
    if not match:
        return None
    return timedelta(
        days=int(match.group(1) or 0),
        hours=int(match.group(2) or 0),
        minutes=int(match.group(3) or 0),
        seconds=int(match.group(4) or 0),
    )


def parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def validate_baseline_freshness(label: str, path: Path, *, strict: bool) -> tuple[list[str], list[str], dict[str, object]]:
    warnings: list[str] = []
    errors: list[str] = []
    metadata: dict[str, object] = {"freshness": "unknown"}
    if not path.exists():
        return warnings, errors, metadata
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return warnings, errors, metadata
    if not isinstance(payload, dict):
        return warnings, errors, metadata

    generated_at = parse_datetime(payload.get("generated_at"))
    ttl = parse_ttl(payload.get("ttl"))
    metadata["generated_at"] = payload.get("generated_at")
    metadata["ttl"] = payload.get("ttl")
    if generated_at is None or ttl is None:
        return warnings, errors, metadata

    expires_at = generated_at + ttl
    metadata["expires_at"] = expires_at.isoformat()
    metadata["freshness"] = "stale" if datetime.now(timezone.utc) > expires_at else "fresh"
    if metadata["freshness"] == "stale":
        message = f"{label} baseline 已过期: generated_at={generated_at.isoformat()}, ttl={payload.get('ttl')}"
        if strict:
            errors.append(message)
        else:
            warnings.append(message)
    return warnings, errors, metadata


def validate_gate5_baseline_freshness(
    baseline_dir: Path,
    *,
    strict: bool,
) -> tuple[list[str], list[str], dict[str, dict[str, object]]]:
    module_warnings, module_errors, module_metadata = validate_baseline_freshness(
        "module-map",
        baseline_dir / "module-map.json",
        strict=strict,
    )
    schema_warnings, schema_errors, schema_metadata = validate_baseline_freshness(
        "schema-context",
        baseline_dir / "schema-context.json",
        strict=strict,
    )
    return (
        module_warnings + schema_warnings,
        module_errors + schema_errors,
        {
            "module_map": module_metadata,
            "schema_context": schema_metadata,
        },
    )


def validate_attached_project_signature(
    module_map_path: Path,
    *,
    attachment_path: Path = DEFAULT_ATTACHMENT_PATH,
    strict: bool,
) -> tuple[list[str], list[str], dict[str, object]]:
    warnings: list[str] = []
    errors: list[str] = []
    metadata: dict[str, object] = {"attachment_signature_status": "unknown"}
    if not attachment_path.exists():
        metadata["attachment_signature_status"] = "no-attachment"
        return warnings, errors, metadata
    try:
        module_map = json.loads(module_map_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return warnings, errors, metadata
    if not isinstance(module_map, dict):
        return warnings, errors, metadata
    recorded_signature = module_map.get("source_signature")
    if not isinstance(recorded_signature, str) or not recorded_signature:
        metadata["attachment_signature_status"] = "missing"
        return warnings, errors, metadata

    current_settings = resolve_module_map_scan_settings(
        attachment_path=attachment_path,
        scan_roots=None,
        design_roots=None,
        project_root=None,
    )
    if current_settings.get("source") != "attachment":
        metadata["attachment_signature_status"] = "no-attachment"
        return warnings, errors, metadata
    current_signature = source_signature(current_settings)
    metadata["attachment_signature_status"] = "matched" if current_signature == recorded_signature else "changed"
    metadata["current_source_signature"] = current_signature
    metadata["recorded_source_signature"] = recorded_signature
    if current_signature != recorded_signature:
        message = "attached project 配置已变化，module-map baseline 需要刷新"
        if strict:
            errors.append(message)
        else:
            warnings.append(message)
    return warnings, errors, metadata


def validate_schema_context_signature(
    schema_context_path: Path,
    *,
    attachment_path: Path = DEFAULT_ATTACHMENT_PATH,
    strict: bool,
) -> tuple[list[str], list[str], dict[str, object]]:
    warnings: list[str] = []
    errors: list[str] = []
    metadata: dict[str, object] = {"schema_context_signature_status": "unknown"}
    if not attachment_path.exists():
        metadata["schema_context_signature_status"] = "no-attachment"
        return warnings, errors, metadata
    try:
        schema_context = json.loads(schema_context_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return warnings, errors, metadata
    if not isinstance(schema_context, dict):
        return warnings, errors, metadata
    recorded_signature = schema_context.get("source_signature")
    if not isinstance(recorded_signature, str) or not recorded_signature:
        metadata["schema_context_signature_status"] = "missing"
        return warnings, errors, metadata

    source = str(schema_context.get("source") or "")
    if source not in {"attachment", "local-fallback", "project_root", "default", "cli"}:
        metadata["schema_context_signature_status"] = "not-applicable"
        return warnings, errors, metadata

    current_settings = resolve_schema_context_sources(
        attachment_path=attachment_path,
        design_roots=None,
        schema_roots=None,
        project_root=None,
    )
    if current_settings.get("source") != "attachment":
        metadata["schema_context_signature_status"] = "no-attachment"
        return warnings, errors, metadata

    expected_payload = dict(schema_context)
    expected_payload["design_roots"] = current_settings.get("design_roots", [])
    expected_payload["schema_roots"] = current_settings.get("schema_roots", [])
    if source != "local-fallback":
        expected_payload["source"] = current_settings.get("source")
    current_signature = schema_context_source_signature(expected_payload)
    metadata["schema_context_signature_status"] = "matched" if current_signature == recorded_signature else "changed"
    metadata["current_schema_source_signature"] = current_signature
    metadata["recorded_schema_source_signature"] = recorded_signature
    if current_signature != recorded_signature:
        message = "schema-context 配置已变化，schema-context baseline 需要刷新"
        if strict:
            errors.append(message)
        else:
            warnings.append(message)
    return warnings, errors, metadata


def analyze_implementation_traceability(
    design_path: Path,
    module_map_path: Path,
    *,
    affected_components: list[str] | None = None,
) -> dict[str, object]:
    design_text = design_path.read_text(encoding="utf-8")
    referenced_classes = extract_referenced_classes(design_text)
    referenced_methods = extract_referenced_method_calls(design_text)
    module_map_quality = read_module_map_quality(module_map_path)
    if not referenced_classes:
        return {
            "result": "WARN",
            "expected_classes": [],
            "implemented_classes": [],
            "design_only_classes": [],
            "missing_classes": [],
            "expected_methods": referenced_methods,
            "matched_methods": [],
            "missing_methods": [],
            "module_map_quality": module_map_quality,
            "message": "设计文档未提取到可追溯的核心类，跳过真实实现映射分析",
        }

    module_entries = extract_module_class_entries(module_map_path, affected_components=affected_components)
    implemented_classes: list[str] = []
    design_only_classes: list[str] = []
    missing_classes: list[str] = []
    ambiguous_classes: list[dict[str, object]] = []
    matched_methods: list[str] = []
    missing_methods: list[str] = []
    method_match_details: list[dict[str, object]] = []

    for class_name in referenced_classes:
        entry = resolve_module_class_entry(module_entries, class_name)
        if not entry:
            candidates = module_class_candidates(module_entries, class_name)
            if len(candidates) > 1:
                ambiguous_classes.append(
                    {
                        "class_name": class_name,
                        "candidate_resource_keys": sorted(
                            {
                                str(item.get("resource_key") or item.get("fqn") or item.get("class_name") or "")
                                for item in candidates
                                if isinstance(item, dict)
                            }
                        ),
                    }
                )
            else:
                missing_classes.append(class_name)
            continue
        source_kind = str(entry.get("source_kind") or "")
        if source_kind.startswith("java"):
            implemented_classes.append(class_name)
        elif source_kind == "design":
            design_only_classes.append(class_name)
        else:
            missing_classes.append(class_name)

    for call in referenced_methods:
        class_name = call["class_name"]
        method_name = call["method_name"]
        entry = resolve_module_class_entry(module_entries, class_name)
        if not entry or not str(entry.get("source_kind") or "").startswith("java"):
            continue
        display_name = f"{class_name}.{call.get('signature') or method_name}"
        match = match_method_call(call, entry)
        method_match_details.append(
            {
                "class_name": class_name,
                "method_name": method_name,
                "expected_signature": match.get("expected_signature"),
                "matched": match.get("matched"),
                "match_mode": match.get("match_mode"),
                "matched_signature": match.get("matched_signature"),
                "candidate_signatures": match.get("candidate_signatures", []),
                "component_id": entry.get("component_id"),
                "resource_key": entry.get("resource_key"),
                "fqn": entry.get("fqn"),
            }
        )
        if match.get("matched"):
            matched_methods.append(display_name)
        else:
            missing_methods.append(display_name)

    low_confidence = str(module_map_quality.get("confidence") or "").lower() == "low"
    result = "PASS" if not design_only_classes and not missing_classes and not ambiguous_classes and not missing_methods and not low_confidence else "WARN"
    method_modes = sorted({str(item.get("match_mode")) for item in method_match_details if item.get("matched") and item.get("match_mode")})
    if result == "PASS":
        if method_modes:
            message = "设计引用类与方法已映射到真实实现来源；方法命中层级=" + ", ".join(method_modes)
        else:
            message = "设计引用类与方法已映射到真实实现来源"
    elif ambiguous_classes:
        ambiguous_names = ", ".join(str(item.get("class_name") or "") for item in ambiguous_classes)
        message = f"璁捐寮曠敤绫诲瓨鍦ㄥ涓?component/resource_key 鍊欓€夛紝鏃犳硶绋冲畾鏄犲皠: {ambiguous_names}"
    elif missing_methods and low_confidence:
        unsupported = module_map_quality.get("unsupported_features") or []
        suffix = ""
        if unsupported:
            suffix = "，unsupported_features=" + ", ".join(str(item) for item in unsupported)
        message = f"设计引用的方法未在真实实现 public_methods/method_details 中找到；module-map 可信度较低，真实实现追溯只能作为弱证据{suffix}"
    elif missing_methods:
        message = "设计引用的方法未在真实实现 public_methods/method_details 中找到"
    elif low_confidence:
        unsupported = module_map_quality.get("unsupported_features") or []
        suffix = ""
        if unsupported:
            suffix = "，unsupported_features=" + ", ".join(str(item) for item in unsupported)
        message = f"module-map 可信度较低，真实实现追溯只能作为弱证据{suffix}"
    else:
        method_modes = sorted({str(item.get("match_mode")) for item in method_match_details if item.get("matched") and item.get("match_mode")})
        message = "设计引用类仍主要来自 design 快照，尚未完全映射到真实实现"

    return {
        "result": result,
        "expected_classes": referenced_classes,
        "implemented_classes": implemented_classes,
        "design_only_classes": design_only_classes,
        "missing_classes": missing_classes,
        "ambiguous_classes": ambiguous_classes,
        "expected_methods": referenced_methods,
        "matched_methods": sorted(set(matched_methods)),
        "missing_methods": sorted(set(missing_methods)),
        "method_match_details": method_match_details,
        "module_map_quality": module_map_quality,
        "message": message,
    }


def resolve_effective_attachment_path(feature_dir: Path, attachment_path: Path = DEFAULT_ATTACHMENT_PATH) -> Path:
    feature_dir = feature_dir.resolve()
    for parent in [feature_dir, *feature_dir.parents]:
        candidate = parent / ".spec" / "attached-project.json"
        if candidate == attachment_path:
            continue
        if candidate.exists():
            return candidate

    attachment = load_attachment_config(attachment_path)
    if attachment:
        for root in attachment.get("design_roots", []):
            if not isinstance(root, str) or not root:
                continue
            root_path = Path(root).resolve()
            try:
                feature_dir.relative_to(root_path)
            except ValueError:
                continue
            return attachment_path

    return feature_dir / ".spec" / "attached-project.json"


def build_implementation_traceability_report_fields(traceability: dict[str, object]) -> dict[str, object]:
    method_match_details = traceability.get("method_match_details")
    if not isinstance(method_match_details, list):
        method_match_details = []
    match_modes = sorted(
        {
            str(item.get("match_mode"))
            for item in method_match_details
            if isinstance(item, dict) and item.get("matched") and item.get("match_mode")
        }
    )
    return {
        "implementation_message": str(traceability.get("message") or ""),
        "implementation_match_modes": match_modes,
        "implementation_method_match_details": method_match_details,
        "implementation_matched_methods": traceability.get("matched_methods", []),
        "implementation_missing_methods": traceability.get("missing_methods", []),
        "implementation_ambiguous_classes": traceability.get("ambiguous_classes", []),
    }


def find_python_runner() -> Path | None:
    for venv_python in [
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / ".venv" / "bin" / "python",
    ]:
        if venv_python.exists():
            return venv_python
    python_cmd = shutil.which("python")
    return Path(python_cmd) if python_cmd else None


def can_import_pytest(python_exe: Path) -> bool:
    result = subprocess.run(
        [str(python_exe), "-c", "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('pytest') else 1)"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def build_junit_wrapper(test_class_name: str, mappings: list[dict[str, object]]) -> str:
    lines = [
        "import org.junit.jupiter.api.Test;",
        "",
        "public class Gate5JUnitWrapper {",
        f"    private final {test_class_name} test = new {test_class_name}();",
        "",
    ]
    seen_methods: set[str] = set()
    for mapping in mappings:
        method_name = str(mapping["test_method"])
        if method_name in seen_methods:
            continue
        seen_methods.add(method_name)
        lines.extend(
            [
                "    @Test",
                f"    public void {method_name}() {{",
                f"        test.{method_name}();",
                "    }",
                "",
            ]
        )
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def build_junit_launcher() -> str:
    return """import java.io.PrintWriter;
import org.junit.platform.engine.discovery.DiscoverySelectors;
import org.junit.platform.launcher.Launcher;
import org.junit.platform.launcher.LauncherDiscoveryRequest;
import org.junit.platform.launcher.core.LauncherDiscoveryRequestBuilder;
import org.junit.platform.launcher.core.LauncherFactory;
import org.junit.platform.launcher.listeners.SummaryGeneratingListener;
import org.junit.platform.launcher.listeners.TestExecutionSummary;

public class Gate5JUnitLauncher {
    public static void main(String[] args) {
        LauncherDiscoveryRequest request = LauncherDiscoveryRequestBuilder.request()
                .selectors(DiscoverySelectors.selectClass(Gate5JUnitWrapper.class))
                .build();
        SummaryGeneratingListener listener = new SummaryGeneratingListener();
        Launcher launcher = LauncherFactory.create();
        launcher.registerTestExecutionListeners(listener);
        launcher.execute(request);

        TestExecutionSummary summary = listener.getSummary();
        summary.printFailuresTo(new PrintWriter(System.err, true));
        long failed = summary.getTestsFailedCount() + summary.getContainersFailedCount();
        if (failed > 0) {
            System.exit(1);
        }
    }
}
"""


def find_latest_jar(group_parts: list[str], artifact: str) -> Path | None:
    base = M2_REPO.joinpath(*group_parts, artifact)
    if not base.exists():
        return None

    def version_key(path: Path) -> tuple:
        version = path.parent.name
        parts = []
        for token in re.split(r"[.-]", version):
            if token.isdigit():
                parts.append((0, int(token)))
            else:
                parts.append((1, token))
        return tuple(parts)

    candidates = sorted(
        (
            path
            for path in base.glob("*/*.jar")
            if path.name.startswith(f"{artifact}-")
            and not path.name.endswith(("-sources.jar", "-javadoc.jar"))
        ),
        key=version_key,
    )
    return candidates[-1] if candidates else None


def junit_classpath_entries() -> list[Path]:
    artifacts = [
        (["org", "junit", "jupiter"], "junit-jupiter-api"),
        (["org", "junit", "jupiter"], "junit-jupiter-engine"),
        (["org", "junit", "platform"], "junit-platform-launcher"),
        (["org", "junit", "platform"], "junit-platform-engine"),
        (["org", "junit", "platform"], "junit-platform-commons"),
        (["org", "apiguardian"], "apiguardian-api"),
        (["org", "opentest4j"], "opentest4j"),
    ]
    jars: list[Path] = []
    for group_parts, artifact in artifacts:
        jar = find_latest_jar(group_parts, artifact)
        if jar is None:
            return []
        jars.append(jar)
    return jars


def build_classpath(entries: list[Path]) -> str:
    return os.pathsep.join(str(entry) for entry in entries)


def attempt_junit_platform_execution(
    test_file: Path,
    mappings: list[dict[str, object]],
    javac: str,
    java_cmd: str,
) -> dict[str, object] | None:
    jars = junit_classpath_entries()
    if not jars:
        return None

    build_dir = test_file.parent / ".gate5_build"
    build_dir.mkdir(parents=True, exist_ok=True)
    wrapper_file = build_dir / "Gate5JUnitWrapper.java"
    launcher_file = build_dir / "Gate5JUnitLauncher.java"
    classpath = build_classpath([build_dir, *jars])

    try:
        compile_test_cmd = [javac, "-cp", classpath, "-d", str(build_dir), str(test_file)]
        compile_test = subprocess.run(compile_test_cmd, check=False, capture_output=True, text=True)
        if compile_test.returncode != 0:
            return {
                "status": "FAIL",
                "mode": "junit-platform-compile",
                "command": compile_test_cmd,
                "returncode": compile_test.returncode,
                "stdout_tail": trim_output(compile_test.stdout),
                "stderr_tail": trim_output(compile_test.stderr),
            }

        atomic_write_text(wrapper_file, build_junit_wrapper(test_file.stem, mappings), encoding="utf-8")
        atomic_write_text(launcher_file, build_junit_launcher(), encoding="utf-8")
        compile_support_cmd = [javac, "-cp", classpath, "-d", str(build_dir), str(wrapper_file), str(launcher_file)]
        compile_support = subprocess.run(compile_support_cmd, check=False, capture_output=True, text=True)
        if compile_support.returncode != 0:
            return {
                "status": "FAIL",
                "mode": "junit-platform-compile",
                "command": compile_support_cmd,
                "returncode": compile_support.returncode,
                "stdout_tail": trim_output(compile_support.stdout),
                "stderr_tail": trim_output(compile_support.stderr),
            }

        run_cmd = [java_cmd, "-ea", "-cp", classpath, "Gate5JUnitLauncher"]
        run_result = subprocess.run(run_cmd, check=False, capture_output=True, text=True)
        return {
            "status": "PASS" if run_result.returncode == 0 else "FAIL",
            "mode": "junit-platform",
            "command": run_cmd,
            "returncode": run_result.returncode,
            "stdout_tail": trim_output(run_result.stdout),
            "stderr_tail": trim_output(run_result.stderr),
        }
    finally:
        try:
            shutil.rmtree(build_dir, ignore_errors=True)
        except OSError:
            pass


def attempt_test_execution(test_file: Path, mappings: list[dict[str, object]]) -> dict[str, object]:
    if test_file.suffix == ".py":
        python_exe = find_python_runner()
        if python_exe is None:
            return {"status": "SKIPPED", "mode": "python", "reason": "未找到可用 Python 解释器"}

        if can_import_pytest(python_exe):
            cmd = [str(python_exe), "-m", "pytest", str(test_file)]
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            return {
                "status": "PASS" if result.returncode == 0 else "FAIL",
                "mode": "pytest",
                "command": cmd,
                "returncode": result.returncode,
                "stdout_tail": trim_output(result.stdout),
                "stderr_tail": trim_output(result.stderr),
            }

        cmd = [str(python_exe), "-m", "unittest", str(test_file)]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if result.returncode == 0 or "No module named" not in result.stderr:
            return {
                "status": "PASS" if result.returncode == 0 else "FAIL",
                "mode": "unittest",
                "command": cmd,
                "returncode": result.returncode,
                "stdout_tail": trim_output(result.stdout),
                "stderr_tail": trim_output(result.stderr),
            }

        return {"status": "SKIPPED", "mode": "python", "reason": "未检测到 pytest/unittest 可执行环境"}

    if test_file.suffix == ".java":
        pom = ROOT / "pom.xml"
        build_gradle = ROOT / "build.gradle"
        build_gradle_kts = ROOT / "build.gradle.kts"

        if pom.exists() and shutil.which("mvn"):
            return {"status": "SKIPPED", "mode": "maven", "reason": "当前未建立设计验证测试到 Maven 测试任务的映射"}
        if (build_gradle.exists() or build_gradle_kts.exists()) and shutil.which("gradle"):
            return {"status": "SKIPPED", "mode": "gradle", "reason": "当前未建立设计验证测试到 Gradle 测试任务的映射"}

        javac = shutil.which("javac")
        if javac:
            java_cmd = shutil.which("java")
            if java_cmd:
                junit_result = attempt_junit_platform_execution(test_file, mappings, javac, java_cmd)
                if junit_result is not None:
                    return junit_result

            build_dir = test_file.parent / ".gate5_build"
            build_dir.mkdir(parents=True, exist_ok=True)
            try:
                compile_test_cmd = [javac, "-d", str(build_dir), str(test_file)]
                compile_test = subprocess.run(compile_test_cmd, check=False, capture_output=True, text=True)
                if compile_test.returncode != 0:
                    return {
                        "status": "FAIL",
                        "mode": "javac",
                        "command": compile_test_cmd,
                        "returncode": compile_test.returncode,
                        "stdout_tail": trim_output(compile_test.stdout),
                        "stderr_tail": trim_output(compile_test.stderr),
                    }

                java_cmd = shutil.which("java")
                if not java_cmd:
                    return {
                        "status": "PASS",
                        "mode": "javac",
                        "command": compile_test_cmd,
                        "returncode": compile_test.returncode,
                        "stdout_tail": trim_output(compile_test.stdout),
                        "stderr_tail": trim_output(compile_test.stderr),
                    }

                run_cmd = [java_cmd, "-ea", "-cp", str(build_dir), test_file.stem]
                run_result = subprocess.run(run_cmd, check=False, capture_output=True, text=True)
                return {
                    "status": "PASS" if run_result.returncode == 0 else "FAIL",
                    "mode": "java-runner",
                    "command": run_cmd,
                    "returncode": run_result.returncode,
                    "stdout_tail": trim_output(run_result.stdout),
                    "stderr_tail": trim_output(run_result.stderr),
                }
            finally:
                try:
                    shutil.rmtree(build_dir, ignore_errors=True)
                except OSError:
                    pass

        return {"status": "SKIPPED", "mode": "java", "reason": "未找到 javac，且仓库缺少 Maven/Gradle 测试载体"}

    return {"status": "SKIPPED", "mode": "unknown", "reason": f"暂不支持的测试文件类型: {test_file.suffix}"}


def summarize_gate5_coverage(content: str, mappings: list[dict[str, object]]) -> tuple[list[str], list[str], list[dict[str, object]], list[str]]:
    uncovered_p0: list[str] = []
    uncovered_p1: list[str] = []
    details: list[dict[str, object]] = []
    placeholder_todos: list[str] = []

    for mapping in mappings:
        req_id = str(mapping["req_id"])
        priority = str(mapping.get("priority", "P1"))
        method_name = str(mapping["test_method"])
        method_present = re.search(rf"\bpublic\s+void\s+{re.escape(method_name)}\s*\(", content) is not None
        placeholder = f"TODO[{req_id}]" in content
        details.append(
            {
                "req_id": req_id,
                "priority": priority,
                "test_method": method_name,
                "covered": method_present,
                "placeholder": placeholder,
            }
        )
        if not method_present:
            if priority == "P0":
                uncovered_p0.append(req_id)
            else:
                uncovered_p1.append(req_id)
        if placeholder:
            placeholder_todos.append(req_id)

    return sorted(set(uncovered_p0)), sorted(set(uncovered_p1)), details, sorted(set(placeholder_todos))


def determine_attached_execution_requirement(
    *,
    risk_tier: str,
    strict_mode: bool,
    explicit_required: bool,
) -> tuple[bool, str]:
    if explicit_required:
        return True, "explicit-cli"
    if strict_mode:
        return True, "strict-mode"
    if risk_tier == "high":
        return True, "high-risk-feature"
    return False, "optional"


def main_for_args(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument(
        "--require-attached-execution",
        action="store_true",
        help="要求附着项目配置并成功执行 verification_commands",
    )
    parser.add_argument("--strict", action="store_true", help="严格模式：要求真实业务验证和实现追溯均通过")
    args = parser.parse_args(argv)

    feature_dir = resolve_feature_dir(args.feature_dir)
    brief_path = feature_dir / "feature-brief.md"
    design_path = detect_latest_design_path(feature_dir)
    reports_dir = reports_dir_for_design(feature_dir, design_path)
    report_path = reports_dir / "gate4-skeleton.json"
    verify_path = reports_dir / "verify-report.json"

    if not report_path.exists():
        print(f"[ERROR] 缺少 Gate 4 报告: {report_path}")
        return 1

    report = json.loads(report_path.read_text(encoding="utf-8"))
    strict_mode = args.strict or os.environ.get("SDD_STRICT", "").lower() in {"1", "true", "yes", "on"}
    brief_content = brief_path.read_text(encoding="utf-8") if brief_path.exists() else ""
    affected_components = extract_affected_components(brief_content) if brief_content else []
    risk_tier = extract_risk_tier(brief_content) if brief_content else "low"
    effective_attachment_path = resolve_effective_attachment_path(feature_dir)
    attached_execution_required, attached_execution_requirement_reason = determine_attached_execution_requirement(
        risk_tier=risk_tier,
        strict_mode=strict_mode,
        explicit_required=args.require_attached_execution,
    )
    test_file = Path(report["test_file"])
    if not test_file.exists():
        print(f"[ERROR] 缺少测试文件: {test_file}")
        return 1

    content = test_file.read_text(encoding="utf-8")
    uncovered_p0, uncovered_p1, details, placeholder_todos = summarize_gate5_coverage(content, report["mappings"])

    result = "PASS"
    if uncovered_p0:
        result = "FAIL"
    elif uncovered_p1:
        result = "WARN"

    execution = attempt_test_execution(test_file, report["mappings"])
    attached_execution = run_attached_verification_commands(
        str(report["feature_name"]),
        attachment_path=effective_attachment_path,
        require_configured=attached_execution_required,
        design_version=str(report.get("design_version") or design_path.name),
        affected_components=affected_components,
    )
    execution_status = str(execution.get("status", "SKIPPED"))
    if execution_status == "FAIL":
        result = "FAIL"
    attached_execution_status = str(attached_execution.get("status", "SKIPPED"))
    if attached_execution_status == "FAIL":
        result = "FAIL"

    baseline_dir = get_active_baseline_dir(create=True, migrate_legacy=True)
    design_pack_dir = resolve_design_pack_dir(feature_dir, reports_dir)
    module_map_path = baseline_dir / "module-map.json"
    schema_context_path = baseline_dir / "schema-context.json"
    expected_req_ids = [
        str(item.get("req_id"))
        for item in report["mappings"]
        if isinstance(item, dict) and isinstance(item.get("req_id"), str) and item.get("req_id")
    ]
    implementation_traceability = analyze_implementation_traceability(
        design_path,
        module_map_path,
        affected_components=affected_components,
    )
    real_test_req_coverage = analyze_real_test_req_coverage(
        expected_req_ids,
        attachment_path=effective_attachment_path,
        affected_components=affected_components,
    )
    if strict_mode and implementation_traceability["result"] != "PASS":
        result = "FAIL"
    baseline_warnings, baseline_errors, baseline_freshness = validate_gate5_baseline_freshness(baseline_dir, strict=strict_mode)
    attachment_warnings, attachment_errors, attachment_signature = validate_attached_project_signature(
        module_map_path,
        attachment_path=effective_attachment_path,
        strict=strict_mode,
    )
    schema_signature_warnings, schema_signature_errors, schema_signature = validate_schema_context_signature(
        schema_context_path,
        attachment_path=effective_attachment_path,
        strict=strict_mode,
    )
    baseline_warnings.extend(attachment_warnings)
    baseline_errors.extend(attachment_errors)
    baseline_warnings.extend(schema_signature_warnings)
    baseline_errors.extend(schema_signature_errors)
    if baseline_errors:
        result = "FAIL"
    elif baseline_warnings and result == "PASS":
        result = "WARN"

    placeholder_warnings = [f"{req_id} 仍包含 TODO 占位符" for req_id in placeholder_todos]

    evidence = {
        "design": {
            "source": str(design_path),
            "hash": hash_file(design_path),
            "evidence_level": "L3",
            "confidence": "medium",
        },
        "module_map": {
            "source": str(module_map_path),
            "hash": hash_file(module_map_path),
            "evidence_level": "L2" if module_map_path.exists() else "L3",
            "confidence": "medium" if module_map_path.exists() else "low",
            **baseline_freshness["module_map"],
            **attachment_signature,
        },
        "schema_context": {
            "source": str(schema_context_path),
            "hash": hash_file(schema_context_path),
            "evidence_level": evidence_level_for_schema_context(schema_context_path),
            "confidence": "medium" if schema_context_path.exists() else "low",
            **baseline_freshness["schema_context"],
            **schema_signature,
        },
    }
    schema_context = {}
    if schema_context_path.exists():
        try:
            loaded_schema_context = json.loads(schema_context_path.read_text(encoding="utf-8"))
            if isinstance(loaded_schema_context, dict):
                schema_context = loaded_schema_context
        except (OSError, json.JSONDecodeError):
            schema_context = {}
    design_resource_claims = build_design_resource_claims_for_pack(
        openapi_path=design_pack_dir / "接口契约.openapi.yaml",
        data_model_path=design_pack_dir / "数据模型.md",
        async_contract_path=design_pack_dir / "异步事件契约.yaml",
        schema_context=schema_context,
        affected_components=affected_components,
        omit_generic_tables_for_exact=False,
    )
    design_resource_claim_summary = summarize_resource_claims(design_resource_claims)
    implementation_report_fields = build_implementation_traceability_report_fields(implementation_traceability)

    verify_report = {
        "feature_name": report["feature_name"],
        "design_version": report["design_version"],
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "test_file": str(test_file),
        "risk_tier": risk_tier,
        "result": result,
        "coverage_result": "FAIL" if uncovered_p0 else ("WARN" if uncovered_p1 else "PASS"),
        "execution": execution,
        "attached_execution": attached_execution,
        "attached_execution_required": attached_execution_required,
        "attached_execution_requirement_reason": attached_execution_requirement_reason,
        "uncovered_p0": uncovered_p0,
        "uncovered_p1": uncovered_p1,
        "design_resource_claims": design_resource_claims,
        "design_resource_claim_summary": design_resource_claim_summary,
        "implementation_result": implementation_traceability["result"],
        **implementation_report_fields,
        "implementation_traceability": implementation_traceability,
        "real_test_req_coverage": real_test_req_coverage,
        "affected_components": affected_components,
        "strict": strict_mode,
        "warnings": baseline_warnings + placeholder_warnings,
        "errors": baseline_errors,
        "placeholder_todos": placeholder_todos,
        "evidence": evidence,
        "details": details,
    }
    with feature_lock(feature_dir, phase="gate5-verify-report"):
        atomic_write_text(verify_path, json.dumps(verify_report, ensure_ascii=False, indent=2), encoding="utf-8")
    gate_report = write_gate_section(
        reports_dir,
        gate_name="gate5",
        feature_name=report["feature_name"],
        design_version=report["design_version"],
        payload={
            "result": result,
            "test_file": str(test_file),
            "risk_tier": risk_tier,
            "coverage_result": verify_report["coverage_result"],
            "execution": execution,
            "attached_execution": attached_execution,
            "attached_execution_required": attached_execution_required,
            "attached_execution_requirement_reason": attached_execution_requirement_reason,
            "uncovered_p0": uncovered_p0,
            "uncovered_p1": uncovered_p1,
            "design_resource_claim_summary": design_resource_claim_summary,
            "design_resource_claim_highlights": design_resource_claim_summary.get("highlights", {}),
            "implementation_result": implementation_traceability["result"],
            **implementation_report_fields,
            "implementation_traceability": implementation_traceability,
            "real_test_req_coverage_result": real_test_req_coverage["result"],
            "strict": strict_mode,
            "warnings": baseline_warnings + placeholder_warnings,
            "errors": baseline_errors,
            "evidence": evidence,
            "report_file": str(verify_path),
        },
    )

    if result == "FAIL":
        print("[FAIL] Gate 5 覆盖验证失败")
        print(f"  - uncovered_p0: {', '.join(sorted(set(uncovered_p0)))}")
        if execution_status == "FAIL":
            print("  - execution: FAIL")
        if attached_execution_status == "FAIL":
            print("  - attached_execution: FAIL")
        print(f"  - report: {verify_path}")
        print(f"  - gate:   {gate_report}")
        return 1

    print(f"[{result}] Gate 5 覆盖验证完成")
    if uncovered_p1:
        print(f"  - uncovered_p1: {', '.join(sorted(set(uncovered_p1)))}")
    print(f"  - execution: {execution_status}")
    print(f"  - attached_execution: {attached_execution_status}")
    if implementation_traceability["result"] != "PASS":
        print(f"  - implementation: {implementation_traceability['result']}")
        print(f"  - note: {implementation_traceability['message']}")
    print(f"  - report: {verify_path}")
    print(f"  - gate:   {gate_report}")
    return 0


def main() -> int:
    return main_for_args()


if __name__ == "__main__":
    raise SystemExit(main())
