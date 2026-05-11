#!/usr/bin/env python3
"""
Language/project adapters for Gate validation.
"""

from __future__ import annotations

import os
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from concurrency import atomic_write_text
from traceability_summaries import (
    summarize_design_class_reliability as _default_summarize_design_class_reliability,
    summarize_design_class_resolution as _default_summarize_design_class_resolution,
    summarize_schema_table_resolution as _default_summarize_schema_table_resolution,
)


ExecutionFn = Callable[[list[str], Path | None], subprocess.CompletedProcess[str]]
TrimFn = Callable[[str, int], str]
ClassExtractorFn = Callable[[str], list[str]]
MethodExtractorFn = Callable[[str], list[dict[str, object]]]
ModuleMapQualityFn = Callable[[Path], dict[str, object]]
ModuleEntryExtractorFn = Callable[[Path, list[str] | None], dict[str, list[dict[str, object]]]]
ModuleEntryResolverFn = Callable[[dict[str, list[dict[str, object]]], str], dict[str, object] | None]
ModuleCandidateFn = Callable[[dict[str, list[dict[str, object]]], str], list[dict[str, object]]]
MethodMatcherFn = Callable[[dict[str, object], dict[str, object]], dict[str, object]]
FrameworkSummaryFn = Callable[[list[dict[str, object]]], dict[str, object]]


def default_execution(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
    )


@dataclass(frozen=True)
class GateAdapterContext:
    repo_root: Path
    m2_repo: Path
    trim_output: TrimFn
    run_command: ExecutionFn = default_execution


@dataclass(frozen=True)
class GateTraceabilityContext:
    extract_referenced_classes: ClassExtractorFn
    extract_referenced_method_calls: MethodExtractorFn
    read_module_map_quality: ModuleMapQualityFn
    extract_module_class_entries: ModuleEntryExtractorFn
    resolve_module_class_entry: ModuleEntryResolverFn
    module_class_candidates: ModuleCandidateFn
    match_method_call: MethodMatcherFn
    summarize_method_framework_evidence: FrameworkSummaryFn


class GateAdapter:
    name = "base"
    supported_suffixes: tuple[str, ...] = ()

    def capabilities(self) -> dict[str, object]:
        return {
            "name": self.name,
            "test_suffixes": list(self.supported_suffixes),
            "implementation_traceability": False,
            "controller_endpoint_extraction": False,
            "design_class_reliability": True,
            "design_class_resolution": True,
            "schema_table_resolution": True,
        }

    def supports_test_file(self, test_file: Path) -> bool:
        return test_file.suffix.lower() in self.supported_suffixes

    def attempt_test_execution(
        self,
        test_file: Path,
        mappings: list[dict[str, object]],
        context: GateAdapterContext,
    ) -> dict[str, object]:
        return {"status": "SKIPPED", "mode": self.name, "reason": f"adapter {self.name} does not execute tests"}

    def supports_implementation_traceability(self, module_map_path: Path) -> bool:
        return False

    def analyze_implementation_traceability(
        self,
        design_path: Path,
        module_map_path: Path,
        *,
        affected_components: list[str] | None,
        context: GateTraceabilityContext,
    ) -> dict[str, object]:
        return {
            "result": "WARN",
            "expected_classes": [],
            "implemented_classes": [],
            "design_only_classes": [],
            "missing_classes": [],
            "expected_methods": [],
            "matched_methods": [],
            "missing_methods": [],
            "module_map_quality": {},
            "message": f"adapter {self.name} does not analyze implementation traceability",
        }

    def extract_controller_endpoints(self, module_map: object) -> list[dict[str, str]]:
        return []

    def summarize_design_class_reliability(
        self,
        module_map: object,
        participant_classes: list[str],
        *,
        affected_components: set[str],
        matches_affected_components,
    ) -> dict[str, object]:
        return _default_summarize_design_class_reliability(
            module_map,
            participant_classes,
            affected_components=affected_components,
            matches_affected_components=matches_affected_components,
        )

    def summarize_design_class_resolution(
        self,
        module_map: object,
        participant_classes: list[str],
        *,
        affected_components: set[str],
        matches_affected_components,
    ) -> dict[str, object]:
        return _default_summarize_design_class_resolution(
            module_map,
            participant_classes,
            affected_components=affected_components,
            matches_affected_components=matches_affected_components,
        )

    def summarize_schema_table_resolution(
        self,
        schema_context: object,
        table_names: list[str],
        *,
        affected_components: set[str],
        extract_schema_table_entries,
        resolve_schema_table_entry,
        schema_table_candidates,
    ) -> dict[str, object]:
        return _default_summarize_schema_table_resolution(
            schema_context,
            table_names,
            affected_components=affected_components,
            extract_schema_table_entries=extract_schema_table_entries,
            resolve_schema_table_entry=resolve_schema_table_entry,
            schema_table_candidates=schema_table_candidates,
        )


class PythonGateAdapter(GateAdapter):
    name = "python"
    supported_suffixes = (".py",)

    def capabilities(self) -> dict[str, object]:
        return {
            **super().capabilities(),
            "implementation_traceability": True,
            "controller_endpoint_extraction": True,
        }

    def supports_implementation_traceability(self, module_map_path: Path) -> bool:
        quality = read_module_map_quality(module_map_path)
        scanner = str(quality.get("scanner") or "").lower()
        return "python" in scanner

    def attempt_test_execution(
        self,
        test_file: Path,
        mappings: list[dict[str, object]],
        context: GateAdapterContext,
    ) -> dict[str, object]:
        python_exe = find_python_runner(context.repo_root)
        if python_exe is None:
            return {"status": "SKIPPED", "mode": "python", "reason": "未找到可用 Python 解释器"}

        if can_import_pytest(python_exe, context):
            cmd = [str(python_exe), "-m", "pytest", str(test_file)]
            result = context.run_command(cmd, None)
            return {
                "status": "PASS" if result.returncode == 0 else "FAIL",
                "mode": "pytest",
                "command": cmd,
                "returncode": result.returncode,
                "stdout_tail": context.trim_output(result.stdout, 1000),
                "stderr_tail": context.trim_output(result.stderr, 1000),
            }

        cmd = [str(python_exe), "-m", "unittest", str(test_file)]
        result = context.run_command(cmd, None)
        if result.returncode == 0 or "No module named" not in result.stderr:
            return {
                "status": "PASS" if result.returncode == 0 else "FAIL",
                "mode": "unittest",
                "command": cmd,
                "returncode": result.returncode,
                "stdout_tail": context.trim_output(result.stdout, 1000),
                "stderr_tail": context.trim_output(result.stderr, 1000),
            }

        return {"status": "SKIPPED", "mode": "python", "reason": "未检测到 pytest/unittest 可执行环境"}
 
    def analyze_implementation_traceability(
        self,
        design_path: Path,
        module_map_path: Path,
        *,
        affected_components: list[str] | None,
        context: GateTraceabilityContext,
    ) -> dict[str, object]:
        design_text = design_path.read_text(encoding="utf-8")
        referenced_classes = context.extract_referenced_classes(design_text)
        referenced_methods = context.extract_referenced_method_calls(design_text)
        module_map_quality = context.read_module_map_quality(module_map_path)
        return {
            "result": "WARN",
            "expected_classes": referenced_classes,
            "implemented_classes": [],
            "design_only_classes": [],
            "missing_classes": [],
            "expected_methods": referenced_methods,
            "matched_methods": [],
            "missing_methods": [],
            "missing_method_details": [],
            "method_match_details": [],
            "method_framework_evidence": context.summarize_method_framework_evidence([]),
            "module_map_quality": module_map_quality,
            "message": "python traceability adapter is not implemented yet",
        }

    def extract_controller_endpoints(self, module_map: object) -> list[dict[str, str]]:
        return extract_controller_endpoints_from_module_map(module_map)


class JavaGateAdapter(GateAdapter):
    name = "java"
    supported_suffixes = (".java",)

    def capabilities(self) -> dict[str, object]:
        return {
            **super().capabilities(),
            "implementation_traceability": True,
            "controller_endpoint_extraction": True,
        }

    def supports_implementation_traceability(self, module_map_path: Path) -> bool:
        quality = read_module_map_quality(module_map_path)
        scanner = str(quality.get("scanner") or "").lower()
        return scanner == "" or "java" in scanner

    def attempt_test_execution(
        self,
        test_file: Path,
        mappings: list[dict[str, object]],
        context: GateAdapterContext,
    ) -> dict[str, object]:
        pom = context.repo_root / "pom.xml"
        build_gradle = context.repo_root / "build.gradle"
        build_gradle_kts = context.repo_root / "build.gradle.kts"

        if pom.exists() and shutil.which("mvn"):
            return {"status": "SKIPPED", "mode": "maven", "reason": "当前未建立设计验证测试到 Maven 测试任务的映射"}
        if (build_gradle.exists() or build_gradle_kts.exists()) and shutil.which("gradle"):
            return {"status": "SKIPPED", "mode": "gradle", "reason": "当前未建立设计验证测试到 Gradle 测试任务的映射"}

        javac = shutil.which("javac")
        if not javac:
            return {"status": "SKIPPED", "mode": "java", "reason": "未找到 javac，且仓库缺少 Maven/Gradle 测试载体"}

        java_cmd = shutil.which("java")
        if java_cmd:
            junit_result = attempt_junit_platform_execution(test_file, mappings, javac, java_cmd, context)
            if junit_result is not None:
                return junit_result

        build_dir = test_file.parent / ".gate5_build"
        build_dir.mkdir(parents=True, exist_ok=True)
        try:
            compile_test_cmd = [javac, "-d", str(build_dir), str(test_file)]
            compile_test = context.run_command(compile_test_cmd, None)
            if compile_test.returncode != 0:
                return {
                    "status": "FAIL",
                    "mode": "javac",
                    "command": compile_test_cmd,
                    "returncode": compile_test.returncode,
                    "stdout_tail": context.trim_output(compile_test.stdout, 1000),
                    "stderr_tail": context.trim_output(compile_test.stderr, 1000),
                }

            if not java_cmd:
                return {
                    "status": "PASS",
                    "mode": "javac",
                    "command": compile_test_cmd,
                    "returncode": compile_test.returncode,
                    "stdout_tail": context.trim_output(compile_test.stdout, 1000),
                    "stderr_tail": context.trim_output(compile_test.stderr, 1000),
                }

            run_cmd = [java_cmd, "-ea", "-cp", str(build_dir), test_file.stem]
            run_result = context.run_command(run_cmd, None)
            return {
                "status": "PASS" if run_result.returncode == 0 else "FAIL",
                "mode": "java-runner",
                "command": run_cmd,
                "returncode": run_result.returncode,
                "stdout_tail": context.trim_output(run_result.stdout, 1000),
                "stderr_tail": context.trim_output(run_result.stderr, 1000),
            }
        finally:
            shutil.rmtree(build_dir, ignore_errors=True)

    def analyze_implementation_traceability(
        self,
        design_path: Path,
        module_map_path: Path,
        *,
        affected_components: list[str] | None,
        context: GateTraceabilityContext,
    ) -> dict[str, object]:
        design_text = design_path.read_text(encoding="utf-8")
        referenced_classes = context.extract_referenced_classes(design_text)
        referenced_methods = context.extract_referenced_method_calls(design_text)
        module_map_quality = context.read_module_map_quality(module_map_path)
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

        module_entries = context.extract_module_class_entries(module_map_path, affected_components)
        implemented_classes: list[str] = []
        design_only_classes: list[str] = []
        missing_classes: list[str] = []
        ambiguous_classes: list[dict[str, object]] = []
        matched_methods: list[str] = []
        missing_methods: list[str] = []
        missing_method_details: list[dict[str, object]] = []
        method_match_details: list[dict[str, object]] = []

        for class_name in referenced_classes:
            entry = context.resolve_module_class_entry(module_entries, class_name)
            if not entry:
                candidates = context.module_class_candidates(module_entries, class_name)
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
            entry = context.resolve_module_class_entry(module_entries, class_name)
            if not entry or not str(entry.get("source_kind") or "").startswith("java"):
                continue
            display_name = f"{class_name}.{call.get('signature') or method_name}"
            match = context.match_method_call(call, entry)
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
        result = "PASS" if not design_only_classes and not missing_classes and not ambiguous_classes and not missing_methods else "WARN"
        method_modes = sorted({str(item.get("match_mode")) for item in method_match_details if item.get("matched") and item.get("match_mode")})
        if result == "PASS":
            if method_modes:
                message = "设计引用类与方法已映射到真实实现来源；方法命中层级=" + ", ".join(method_modes)
            else:
                message = "设计引用类与方法已映射到真实实现来源"
        elif ambiguous_classes:
            ambiguous_names = ", ".join(str(item.get("class_name") or "") for item in ambiguous_classes)
            message = f"设计引用类存在多个 component/resource_key 候选，无法稳定映射: {ambiguous_names}"
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
            "method_framework_evidence": context.summarize_method_framework_evidence(method_match_details),
            "module_map_quality": module_map_quality,
            "message": message,
        }

    def extract_controller_endpoints(self, module_map: object) -> list[dict[str, str]]:
        return extract_controller_endpoints_from_module_map(module_map)


class GateAdapterRegistry:
    def __init__(self, adapters: list[GateAdapter]) -> None:
        self.adapters = adapters

    def select_for_test_file(self, test_file: Path) -> GateAdapter | None:
        for adapter in self.adapters:
            if adapter.supports_test_file(test_file):
                return adapter
        return None

    def select_for_implementation_traceability(self, module_map_path: Path) -> GateAdapter | None:
        for adapter in self.adapters:
            if adapter.supports_implementation_traceability(module_map_path):
                return adapter
        return None

    def select_for_module_map(self, module_map: object) -> GateAdapter | None:
        if isinstance(module_map, dict):
            scanner = str(module_map.get("scanner") or "").lower()
            if "python" in scanner:
                for adapter in self.adapters:
                    if isinstance(adapter, PythonGateAdapter):
                        return adapter
            if "java" in scanner or scanner == "":
                for adapter in self.adapters:
                    if isinstance(adapter, JavaGateAdapter):
                        return adapter
        return None

    def capability_summary(self) -> list[dict[str, object]]:
        return [adapter.capabilities() for adapter in self.adapters]


def default_gate_adapter_registry() -> GateAdapterRegistry:
    return GateAdapterRegistry([PythonGateAdapter(), JavaGateAdapter()])


def normalize_type_name(value: object) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text:
        return ""
    text = re.sub(r"<.*?>", "", text)
    text = text.replace("...", "[]")
    text = text.split(".")[-1]
    return text.strip()


def extract_referenced_classes(design_text: str, extract_mermaid_participants: ClassExtractorFn) -> list[str]:
    return extract_mermaid_participants(design_text)


def split_top_level_args(text: str) -> list[str]:
    depth = 0
    current: list[str] = []
    parts: list[str] = []
    for char in text:
        if char == "<":
            depth += 1
        elif char == ">" and depth > 0:
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    if current:
        parts.append("".join(current))
    return parts


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
            parameter_types = parameter_hints_from_freeform_args(args_text)
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


def normalize_endpoint_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    normalized = value.strip()
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    return re.sub(r"/+", "/", normalized.rstrip("/") or "/")


def normalize_http_method(value: object) -> str:
    return str(value or "").strip().upper()


def extract_controller_endpoints_from_module_map(module_map: object) -> list[dict[str, str]]:
    if not isinstance(module_map, dict):
        return []
    endpoints: list[dict[str, str]] = []
    for item in module_map.get("classes", []):
        if not isinstance(item, dict):
            continue
        class_name = str(item.get("simple_name") or item.get("class_name") or "")
        component_id = str(item.get("component_id") or "")
        resource_key = str(item.get("resource_key") or item.get("fqn") or class_name)
        for endpoint in item.get("endpoints", []):
            if not isinstance(endpoint, dict):
                continue
            path = normalize_endpoint_path(endpoint.get("path"))
            method = normalize_http_method(endpoint.get("method"))
            if not path or not method:
                continue
            endpoints.append(
                {
                    "path": path,
                    "method": method,
                    "operation_id": str(endpoint.get("operation_id") or endpoint.get("method_name") or ""),
                    "method_name": str(endpoint.get("method_name") or ""),
                    "class_name": class_name,
                    "component_id": component_id,
                    "resource_key": resource_key,
                }
            )
    return endpoints


def merge_schema_table_entry(existing: dict[str, object] | None, table: dict[str, object]) -> dict[str, object]:
    if not isinstance(existing, dict):
        merged = dict(table)
        if isinstance(merged.get("resource_key"), str):
            merged["resource_keys"] = [str(merged["resource_key"])]
        return merged

    merged = dict(existing)
    for field in ("columns", "declared_columns", "sql_columns", "indexed_columns", "sources"):
        merged[field] = sorted(set(merged.get(field, [])) | set(table.get(field, [])))
    column_details = list(merged.get("column_details", []))
    for detail in table.get("column_details", []):
        if isinstance(detail, dict) and detail not in column_details:
            column_details.append(detail)
    merged["column_details"] = column_details
    resource_keys = set(merged.get("resource_keys", []))
    if isinstance(merged.get("resource_key"), str):
        resource_keys.add(str(merged["resource_key"]))
    if isinstance(table.get("resource_key"), str):
        resource_keys.add(str(table["resource_key"]))
    merged["resource_keys"] = sorted(resource_keys)
    for key in ("component_id", "db_type", "connection_name", "schema_name", "resource_key"):
        if not merged.get(key) and table.get(key):
            merged[key] = table.get(key)
    return merged


def build_schema_table_aliases(table: dict[str, object]) -> list[str]:
    aliases: list[str] = []
    table_name = table.get("table_name")
    resource_key = table.get("resource_key")
    if isinstance(table_name, str) and table_name:
        aliases.append(table_name)
        aliases.append(table_name.lower())
    if isinstance(resource_key, str) and resource_key:
        aliases.append(resource_key)
        tail = resource_key.split("::")[-1]
        aliases.append(tail)
        aliases.append(tail.lower())
    deduped: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        if alias and alias not in seen:
            seen.add(alias)
            deduped.append(alias)
    return deduped


def extract_schema_table_entries(
    schema_context: object,
    affected_components: set[str],
    matches_affected_components,
) -> dict[str, list[dict[str, object]]]:
    if not isinstance(schema_context, dict):
        return {}
    aliases: dict[str, list[dict[str, object]]] = {}
    canonical_entries: dict[str, dict[str, object]] = {}
    for table in schema_context.get("tables", []):
        if not isinstance(table, dict):
            continue
        if not isinstance(table.get("table_name"), str):
            continue
        if not matches_affected_components(table, affected_components):
            continue
        canonical_key = str(table.get("resource_key") or table.get("table_name") or "")
        canonical_entries[canonical_key] = merge_schema_table_entry(canonical_entries.get(canonical_key), dict(table))
    for entry in canonical_entries.values():
        for alias in build_schema_table_aliases(entry):
            aliases.setdefault(alias, []).append(entry)
    return aliases


def resolve_schema_table_entry(entries: dict[str, list[dict[str, object]]], table_name: str) -> dict[str, object] | None:
    candidates = entries.get(table_name) or entries.get(table_name.lower()) or []
    if len(candidates) == 1:
        return candidates[0]
    return None


def schema_table_candidates(entries: dict[str, list[dict[str, object]]], table_name: str) -> list[dict[str, object]]:
    return entries.get(table_name) or entries.get(table_name.lower()) or []


def parameter_hints_from_freeform_args(args_text: str) -> list[str]:
    hints: list[str] = []
    for item in split_top_level_args(args_text):
        candidate = item.strip()
        if not candidate or " " not in candidate:
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
            indexed_item = dict(item)
            indexed_item["name"] = str(name or "")
            indexed_item["signature"] = str(signature or "")
            indexed_item["parameter_types"] = [normalize_type_name(param) for param in parameter_types if isinstance(param, str)]
            indexed.append(indexed_item)
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
            "matched_method_detail": None,
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
                    "matched_method_detail": candidate,
                }
        return {
            "matched": False,
            "match_mode": "signature",
            "expected_signature": str(call.get("signature") or method_name),
            "matched_signature": None,
            "candidate_signatures": [item.get("signature") for item in candidates if item.get("signature")],
            "matched_method_detail": None,
        }
    if expected_parameter_count:
        matched_candidates = [candidate for candidate in candidates if len(candidate.get("parameter_types", [])) == expected_parameter_count]
        if len(matched_candidates) == 1:
            candidate = matched_candidates[0]
            return {
                "matched": True,
                "match_mode": "arity",
                "expected_signature": str(call.get("signature") or method_name),
                "matched_signature": candidate.get("signature"),
                "candidate_signatures": [item.get("signature") for item in candidates if item.get("signature")],
                "matched_method_detail": candidate,
            }
        return {
            "matched": False,
            "match_mode": "arity",
            "expected_signature": str(call.get("signature") or method_name),
            "matched_signature": None,
            "candidate_signatures": [item.get("signature") for item in candidates if item.get("signature")],
            "matched_method_detail": None,
        }
    if len(candidates) == 1:
        candidate = candidates[0]
        return {
            "matched": True,
            "match_mode": "name",
            "expected_signature": str(call.get("signature") or method_name),
            "matched_signature": candidate.get("signature"),
            "candidate_signatures": [item.get("signature") for item in candidates if item.get("signature")],
            "matched_method_detail": candidate,
        }
    return {
        "matched": False,
        "match_mode": "name",
        "expected_signature": str(call.get("signature") or method_name),
        "matched_signature": None,
        "candidate_signatures": [item.get("signature") for item in candidates if item.get("signature")],
        "matched_method_detail": None,
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
    if not merged.get("scan_reliability") and isinstance(node.get("scan_reliability"), dict):
        merged["scan_reliability"] = dict(node.get("scan_reliability"))
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


def matches_affected_component(node: dict[str, object], affected_components: set[str]) -> bool:
    if not affected_components:
        return True
    candidate_values = []
    for key in ("component_id", "resource_key", "fqn", "simple_name", "class_name", "display_name", "name"):
        value = node.get(key)
        if isinstance(value, str) and value:
            candidate_values.append(value)
            candidate_values.append(value.split(".")[-1])
            if "::" in value:
                candidate_values.append(value.split("::")[-1])
                candidate_values.append(value.split("::")[-1].split(".")[-1])
    return any(candidate in affected_components for candidate in candidate_values)


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
                if matches_affected_component(node, affected_component_set):
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
    exact_fqn = [item for item in candidates if str(item.get("fqn") or "") == class_name]
    if len(exact_fqn) == 1:
        return exact_fqn[0]
    exact_resource_key = [item for item in candidates if str(item.get("resource_key") or "") == class_name]
    if len(exact_resource_key) == 1:
        return exact_resource_key[0]
    java_candidates = [item for item in candidates if str(item.get("source_kind") or "").startswith("java")]
    if len(java_candidates) == 1 and len(candidates) == 1:
        return java_candidates[0]
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


def find_python_runner(repo_root: Path) -> Path | None:
    for venv_python in [
        repo_root / ".venv" / "Scripts" / "python.exe",
        repo_root / ".venv" / "bin" / "python",
    ]:
        if venv_python.exists():
            return venv_python
    python_cmd = shutil.which("python")
    return Path(python_cmd) if python_cmd else None


def can_import_pytest(python_exe: Path, context: GateAdapterContext) -> bool:
    result = context.run_command(
        [str(python_exe), "-c", "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('pytest') else 1)"],
        None,
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


def find_latest_jar(m2_repo: Path, group_parts: list[str], artifact: str) -> Path | None:
    base = m2_repo.joinpath(*group_parts, artifact)
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


def junit_classpath_entries(m2_repo: Path) -> list[Path]:
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
        jar = find_latest_jar(m2_repo, group_parts, artifact)
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
    context: GateAdapterContext,
) -> dict[str, object] | None:
    jars = junit_classpath_entries(context.m2_repo)
    if not jars:
        return None

    build_dir = test_file.parent / ".gate5_build"
    build_dir.mkdir(parents=True, exist_ok=True)
    wrapper_file = build_dir / "Gate5JUnitWrapper.java"
    launcher_file = build_dir / "Gate5JUnitLauncher.java"
    classpath = build_classpath([build_dir, *jars])

    try:
        compile_test_cmd = [javac, "-cp", classpath, "-d", str(build_dir), str(test_file)]
        compile_test = context.run_command(compile_test_cmd, None)
        if compile_test.returncode != 0:
            return {
                "status": "FAIL",
                "mode": "junit-platform-compile",
                "command": compile_test_cmd,
                "returncode": compile_test.returncode,
                "stdout_tail": context.trim_output(compile_test.stdout, 1000),
                "stderr_tail": context.trim_output(compile_test.stderr, 1000),
            }

        atomic_write_text(wrapper_file, build_junit_wrapper(test_file.stem, mappings), encoding="utf-8")
        atomic_write_text(launcher_file, build_junit_launcher(), encoding="utf-8")
        compile_support_cmd = [javac, "-cp", classpath, "-d", str(build_dir), str(wrapper_file), str(launcher_file)]
        compile_support = context.run_command(compile_support_cmd, None)
        if compile_support.returncode != 0:
            return {
                "status": "FAIL",
                "mode": "junit-platform-compile",
                "command": compile_support_cmd,
                "returncode": compile_support.returncode,
                "stdout_tail": context.trim_output(compile_support.stdout, 1000),
                "stderr_tail": context.trim_output(compile_support.stderr, 1000),
            }

        run_cmd = [java_cmd, "-ea", "-cp", classpath, "Gate5JUnitLauncher"]
        run_result = context.run_command(run_cmd, None)
        return {
            "status": "PASS" if run_result.returncode == 0 else "FAIL",
            "mode": "junit-platform",
            "command": run_cmd,
            "returncode": run_result.returncode,
            "stdout_tail": context.trim_output(run_result.stdout, 1000),
            "stderr_tail": context.trim_output(run_result.stderr, 1000),
        }
    finally:
        shutil.rmtree(build_dir, ignore_errors=True)
