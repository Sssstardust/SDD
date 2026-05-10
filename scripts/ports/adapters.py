#!/usr/bin/env python3
"""
Ports-layer bridge exports.
"""

from __future__ import annotations

from attached_project import (
    DEFAULT_ATTACHMENT_PATH,
    build_workspace_payload,
    load_attachment_config,
    save_attachment_config,
)
from gate_adapters import (
    GateAdapter,
    GateAdapterContext,
    GateAdapterRegistry,
    GateTraceabilityContext,
    JavaGateAdapter,
    PythonGateAdapter,
    default_gate_adapter_registry,
)
from polyquery_adapter import (
    DEFAULT_CONFIG_PATH,
    polyquery_list_tables,
    polyquery_schema_for_feature,
)

__all__ = [
    "DEFAULT_ATTACHMENT_PATH",
    "DEFAULT_CONFIG_PATH",
    "build_workspace_payload",
    "load_attachment_config",
    "save_attachment_config",
    "GateAdapter",
    "GateAdapterContext",
    "GateAdapterRegistry",
    "GateTraceabilityContext",
    "JavaGateAdapter",
    "PythonGateAdapter",
    "default_gate_adapter_registry",
    "polyquery_list_tables",
    "polyquery_schema_for_feature",
]
