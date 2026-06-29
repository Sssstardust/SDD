#!/usr/bin/env python3
"""
Language/project adapters for Gate validation.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


ExecutionFn = Callable[[list[str], Path | None], subprocess.CompletedProcess[str]]
TrimFn = Callable[[str, int], str]


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
    extract_referenced_classes: Callable[[str], list[str]]
    extract_referenced_method_calls: Callable[[str], list[dict[str, object]]]
    read_module_map_quality: Callable[[Path], dict[str, object]]
    extract_module_class_entries: Callable[[Path, list[str] | None], dict[str, list[dict[str, object]]]]
    resolve_module_class_entry: Callable[[dict[str, list[dict[str, object]]], str], dict[str, object] | None]
    module_class_candidates: Callable[[dict[str, list[dict[str, object]]], str], list[dict[str, object]]]
    match_method_call: Callable[[dict[str, object], dict[str, object]], dict[str, object]]
    summarize_method_framework_evidence: Callable[[list[dict[str, object]]], dict[str, object]]


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
        traceability_context: GateTraceabilityContext,
        verbose: bool = False,
    ) -> dict[str, object]:
        return {}


class PythonGateAdapter(GateAdapter):
    name = "python"
    supported_suffixes = (".py",)

    def capabilities(self) -> dict[str, object]:
        caps = super().capabilities()
        caps["implementation_traceability"] = True
        return caps


class JavaGateAdapter(GateAdapter):
    name = "java"
    supported_suffixes = (".java",)

    def capabilities(self) -> dict[str, object]:
        caps = super().capabilities()
        caps["implementation_traceability"] = True
        return caps


class GateAdapterRegistry:
    def __init__(self, adapters: list[GateAdapter]) -> None:
        self.adapters = adapters

    def select_for_test_file(self, test_file: Path) -> GateAdapter | None:
        for adapter in self.adapters:
            if adapter.supports_test_file(test_file):
                return adapter
        return None


def default_gate_adapter_registry() -> GateAdapterRegistry:
    return GateAdapterRegistry([PythonGateAdapter(), JavaGateAdapter()])
