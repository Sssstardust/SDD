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
from datetime import datetime, timezone
from pathlib import Path

from domain.attached_project import DEFAULT_ATTACHMENT_PATH, load_attachment_config
from infrastructure.baseline_validators import (
    parse_datetime,
    parse_ttl,
    validate_attached_project_signature,
    validate_baseline_freshness,
    validate_schema_context_signature,
)
from infrastructure.baseline_extractors import build_design_resource_claims_for_pack, extract_mermaid_participants, summarize_resource_claims
from infrastructure.baseline_paths import get_active_baseline_dir
from infrastructure.concurrency import atomic_write_text, feature_lock
from infrastructure.design_evidence import evidence_level_for_schema_context, hash_file, resolve_design_pack_dir
from domain.baseline import ModuleMapDocument, SchemaContextDocument
from application.feature_brief import extract_affected_components, extract_risk_tier
from gate_adapters import (
    GateAdapterContext,
    GateTraceabilityContext,
    build_method_detail_index as _build_method_detail_index,
    build_module_entry_aliases as _build_module_entry_aliases,
    default_gate_adapter_registry,
    extract_referenced_classes as _extract_referenced_classes,
    extract_referenced_method_calls as _extract_referenced_method_calls,
    extract_module_class_entries as _extract_module_class_entries,
    match_method_call as _match_method_call,
    merge_module_entry as _merge_module_entry,
    module_class_candidates as _module_class_candidates,
    read_module_map_quality as _read_module_map_quality,
    resolve_module_class_entry as _resolve_module_class_entry,
)
from application.gate5_admissions import summarize_gate5_admissions
from infrastructure.gate_report import write_gate_section
from gates.gate5_reporter import build_gate5_section_payload
from application.traceability_summaries import (
    build_implementation_traceability_report_fields as _build_implementation_traceability_report_fields,
    summarize_method_framework_evidence as _summarize_method_framework_evidence,
)
from infrastructure.versioning import detect_latest_design_path, reports_dir_for_design, resolve_feature_dir


ROOT = Path(__file__).resolve().parent.parent
M2_REPO = Path.home() / ".m2" / "repository"


def summarize_method_framework_evidence(method_match_details: list[dict[str, object]]) -> dict[str, object]:
    return _summarize_method_framework_evidence(method_match_details)


def build_implementation_traceability_report_fields(traceability: dict[str, object]) -> dict[str, object]:
    return _build_implementation_traceability_report_fields(traceability)


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
    return _extract_referenced_classes(design_text, extract_mermaid_participants)


def extract_referenced_method_calls(design_text: str) -> list[dict[str, object]]:
    return _extract_referenced_method_calls(design_text)


def build_method_detail_index(entry: dict[str, object]) -> list[dict[str, object]]:
    return _build_method_detail_index(entry)


def match_method_call(call: dict[str, object], entry: dict[str, object]) -> dict[str, object]:
    return _match_method_call(call, entry)




def merge_module_entry(existing: dict[str, object], node: dict[str, object]) -> dict[str, object]:
    return _merge_module_entry(existing, node)


def build_module_entry_aliases(node: dict[str, object]) -> list[str]:
    return _build_module_entry_aliases(node)


def extract_module_class_entries(
    module_map_path: Path,
    *,
    affected_components: list[str] | None = None,
) -> dict[str, list[dict[str, object]]]:
    return _extract_module_class_entries(module_map_path, affected_components=affected_components)


def resolve_module_class_entry(entries: dict[str, list[dict[str, object]]], class_name: str) -> dict[str, object] | None:
    return _resolve_module_class_entry(entries, class_name)


def module_class_candidates(entries: dict[str, list[dict[str, object]]], class_name: str) -> list[dict[str, object]]:
    return _module_class_candidates(entries, class_name)


def read_module_map_quality(module_map_path: Path) -> dict[str, object]:
    quality = _read_module_map_quality(module_map_path)
    module_map_payload = quality.get("module_map")
    if isinstance(module_map_payload, dict):
        module_map_doc = ModuleMapDocument.from_payload(module_map_payload)
        quality.setdefault("scanner", module_map_doc.scanner)
        quality.setdefault("confidence", module_map_doc.confidence)
    return quality


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




def analyze_implementation_traceability(
    design_path: Path,
    module_map_path: Path,
    *,
    affected_components: list[str] | None = None,
) -> dict[str, object]:
    adapter = default_gate_adapter_registry().select_for_implementation_traceability(module_map_path)
    if adapter is not None:
        return adapter.analyze_implementation_traceability(
            design_path,
            module_map_path,
            affected_components=affected_components,
            context=GateTraceabilityContext(
                extract_referenced_classes=extract_referenced_classes,
                extract_referenced_method_calls=extract_referenced_method_calls,
                read_module_map_quality=read_module_map_quality,
                extract_module_class_entries=lambda path, components: extract_module_class_entries(path, affected_components=components),
                resolve_module_class_entry=resolve_module_class_entry,
                module_class_candidates=module_class_candidates,
                match_method_call=match_method_call,
                summarize_method_framework_evidence=summarize_method_framework_evidence,
            ),
        )

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
    missing_method_details: list[dict[str, object]] = []
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
                        "candidate_components": sorted(
                            {
                                str(item.get("component_id") or "")
                                for item in candidates
                                if isinstance(item, dict) and str(item.get("component_id") or "")
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
                "scan_reliability": entry.get("scan_reliability"),
                "matched_method_detail": match.get("matched_method_detail"),
            }
        )
        if match.get("matched"):
            matched_methods.append(display_name)
        else:
            missing_methods.append(display_name)
            missing_method_details.append(
                {
                    "class_name": class_name,
                    "method_name": method_name,
                    "expected_signature": match.get("expected_signature"),
                    "candidate_signatures": match.get("candidate_signatures", []),
                    "component_id": entry.get("component_id"),
                    "resource_key": entry.get("resource_key"),
                    "fqn": entry.get("fqn"),
                    "scan_reliability": entry.get("scan_reliability"),
                }
            )

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
        "missing_method_details": missing_method_details,
        "method_match_details": method_match_details,
        "method_framework_evidence": summarize_method_framework_evidence(method_match_details),
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
    adapter = default_gate_adapter_registry().select_for_test_file(test_file)
    if adapter is None:
        return {"status": "SKIPPED", "mode": "unknown", "reason": f"暂不支持的测试文件类型: {test_file.suffix}"}
    return adapter.attempt_test_execution(
        test_file,
        mappings,
        GateAdapterContext(repo_root=ROOT, m2_repo=M2_REPO, trim_output=trim_output),
    )


def attempt_test_execution_legacy(test_file: Path, mappings: list[dict[str, object]]) -> dict[str, object]:
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


def evaluate_real_test_req_admission(
    mappings: list[dict[str, object]],
    real_test_req_coverage: dict[str, object],
    *,
    risk_tier: str,
) -> dict[str, object]:
    expected_req_ids = [
        str(item.get("req_id"))
        for item in mappings
        if isinstance(item, dict) and isinstance(item.get("req_id"), str) and item.get("req_id")
    ]
    required_req_ids = expected_req_ids
    requirement = "all-req"
    if risk_tier == "high":
        required_req_ids = [
            str(item.get("req_id"))
            for item in mappings
            if isinstance(item, dict)
            and isinstance(item.get("req_id"), str)
            and item.get("req_id")
            and str(item.get("priority") or "").upper() == "P0"
        ]
        requirement = "high-risk-p0-req"

    covered_req_ids = set(
        str(item)
        for item in real_test_req_coverage.get("covered_req_ids", [])
        if isinstance(item, str) and item
    ) if isinstance(real_test_req_coverage, dict) else set()
    missing_required_req_ids = sorted(req_id for req_id in required_req_ids if req_id not in covered_req_ids)

    if not required_req_ids:
        result = "PASS"
        message = "no required req ids for real-test admission"
    elif missing_required_req_ids:
        result = "FAIL" if risk_tier == "high" else "WARN"
        message = (
            "high-risk feature requires real-test coverage for all P0 req ids"
            if risk_tier == "high"
            else "real-test coverage is missing required req ids"
        )
    else:
        result = "PASS"
        message = "real-test req admission passed"

    return {
        "result": result,
        "requirement": requirement,
        "required_req_ids": required_req_ids,
        "missing_required_req_ids": missing_required_req_ids,
        "message": message,
    }


def evaluate_attached_execution_admission(
    attached_execution: dict[str, object],
    *,
    required: bool,
    requirement_reason: str,
) -> dict[str, object]:
    status = str(attached_execution.get("status") or "SKIPPED") if isinstance(attached_execution, dict) else "SKIPPED"
    commands = attached_execution.get("commands", []) if isinstance(attached_execution, dict) else []
    components = attached_execution.get("components", []) if isinstance(attached_execution, dict) else []
    failed_components = [
        str(item.get("component_id"))
        for item in components
        if isinstance(item, dict)
        and item.get("component_id")
        and str(item.get("status") or "") == "FAIL"
    ] if isinstance(components, list) else []
    failed_commands = [
        str(item.get("name") or item.get("command") or "")
        for item in commands
        if isinstance(item, dict) and str(item.get("status") or "") == "FAIL"
    ] if isinstance(commands, list) else []
    command_count = len(commands) if isinstance(commands, list) else 0

    if status == "FAIL":
        result = "FAIL"
        message = "attached execution failed"
    elif required and status != "PASS":
        result = "FAIL"
        message = "attached execution is required but did not pass"
    elif status == "PASS":
        result = "PASS"
        message = "attached execution admission passed"
    else:
        result = "SKIPPED"
        message = "attached execution is optional and was skipped"

    return {
        "result": result,
        "required": required,
        "requirement_reason": requirement_reason,
        "execution_status": status,
        "command_count": command_count,
        "failed_components": sorted(set(failed_components)),
        "failed_commands": [item for item in failed_commands if item],
        "message": message,
    }


def evaluate_affected_component_execution_admission(
    attached_execution: dict[str, object],
    *,
    affected_components: list[str],
    required: bool,
) -> dict[str, object]:
    required_components = sorted({item for item in affected_components if item})
    components = attached_execution.get("components", []) if isinstance(attached_execution, dict) else []
    component_statuses: dict[str, str] = {}
    if isinstance(components, list):
        for item in components:
            if not isinstance(item, dict):
                continue
            component_id = str(item.get("component_id") or "")
            if not component_id:
                continue
            component_statuses[component_id] = str(item.get("status") or "UNKNOWN")

    missing_components = sorted(component_id for component_id in required_components if component_id not in component_statuses)
    failed_components = sorted(
        component_id
        for component_id in required_components
        if component_statuses.get(component_id) == "FAIL"
    )

    if not required_components:
        result = "PASS"
        message = "no affected components declared for execution admission"
    elif missing_components and required:
        result = "FAIL"
        message = "affected components require component-level attached execution evidence"
    elif failed_components:
        result = "FAIL"
        message = "affected component attached execution failed"
    elif missing_components:
        result = "WARN"
        message = "affected components are missing component-level attached execution evidence"
    else:
        result = "PASS"
        message = "affected component execution admission passed"

    return {
        "result": result,
        "required": required,
        "required_components": required_components,
        "covered_components": sorted(component_id for component_id in required_components if component_statuses.get(component_id) == "PASS"),
        "missing_components": missing_components,
        "failed_components": failed_components,
        "message": message,
    }


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
    attached_execution_admission = evaluate_attached_execution_admission(
        attached_execution,
        required=attached_execution_required,
        requirement_reason=attached_execution_requirement_reason,
    )
    if attached_execution_admission["result"] == "FAIL":
        result = "FAIL"
    affected_component_execution_admission = evaluate_affected_component_execution_admission(
        attached_execution,
        affected_components=affected_components,
        required=attached_execution_required,
    )
    if affected_component_execution_admission["result"] == "FAIL":
        result = "FAIL"
    elif affected_component_execution_admission["result"] == "WARN" and result == "PASS":
        result = "WARN"

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
    real_test_req_admission = evaluate_real_test_req_admission(
        report["mappings"],
        real_test_req_coverage,
        risk_tier=risk_tier,
    )
    gate5_admission_summary = summarize_gate5_admissions(
        real_test_req_admission=real_test_req_admission,
        attached_execution_admission=attached_execution_admission,
        affected_component_execution_admission=affected_component_execution_admission,
    )
    if strict_mode and implementation_traceability["result"] != "PASS":
        result = "FAIL"
    if real_test_req_admission["result"] == "FAIL":
        result = "FAIL"
    elif real_test_req_admission["result"] == "WARN" and result == "PASS":
        result = "WARN"
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
                schema_context_doc = SchemaContextDocument.from_payload(loaded_schema_context)
                schema_context.setdefault("component_ids", list(schema_context_doc.component_ids))
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
        "attached_execution_admission": attached_execution_admission,
        "affected_component_execution_admission": affected_component_execution_admission,
        "uncovered_p0": uncovered_p0,
        "uncovered_p1": uncovered_p1,
        "design_resource_claims": design_resource_claims,
        "design_resource_claim_summary": design_resource_claim_summary,
        "implementation_result": implementation_traceability["result"],
        **implementation_report_fields,
        "implementation_traceability": implementation_traceability,
        "real_test_req_coverage": real_test_req_coverage,
        "real_test_req_admission": real_test_req_admission,
        "gate5_admission_summary": gate5_admission_summary,
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
        payload=build_gate5_section_payload(
            result=result,
            test_file=str(test_file),
            risk_tier=risk_tier,
            coverage_result=verify_report["coverage_result"],
            execution=execution,
            attached_execution=attached_execution,
            attached_execution_required=attached_execution_required,
            attached_execution_requirement_reason=attached_execution_requirement_reason,
            attached_execution_admission=attached_execution_admission,
            affected_component_execution_admission=affected_component_execution_admission,
            uncovered_p0=uncovered_p0,
            uncovered_p1=uncovered_p1,
            design_resource_claim_summary=design_resource_claim_summary,
            implementation_result=implementation_traceability["result"],
            implementation_report_fields=implementation_report_fields,
            implementation_traceability=implementation_traceability,
            real_test_req_coverage_result=real_test_req_coverage["result"],
            real_test_req_admission=real_test_req_admission,
            gate5_admission_summary=gate5_admission_summary,
            strict=strict_mode,
            warnings=baseline_warnings + placeholder_warnings,
            errors=baseline_errors,
            evidence=evidence,
            report_file=str(verify_path),
        ),
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
