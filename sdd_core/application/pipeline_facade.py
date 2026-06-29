#!/usr/bin/env python3
"""
Facade entrance for pipeline command actions.
Delegates to modular sub-modules under application layer (FIX-016).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

# Setup system path to resolve internal modules correctly
PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


from sdd_core.application.pipeline_state import (
    ROOT,
    DOC_TEMPLATES,
    set_json_mode,
    reset_execution_trace,
    console_print,
    record_execution,
    run_traced_captured_command,
    run_external_command,
    _run_steps_compat,
    build_pipeline_run_context,
    extract_issue_lines,
    collect_trace_warnings,
    collect_trace_errors,
)

from sdd_core.application.pipeline_commands import (
    init_feature,
    bootstrap,
    generate_feature_brief,
    init_design,
    generate_design,
    check_design,
    init_design_pack,
    check_design_pack,
    gate1,
    gate2,
    gate3,
    init_approval,
    approve_design,
    check_approval,
    update_design_index,
    generate_task_slices,
    gate4,
    gate5,
    release_gate,
    check_arch_standards_sync,
    cancel_design,
    archive_design,
    sync_baseline,
    refresh_module_map,
    attach_project,
    onboard_project,
    refresh_schema_context,
    refresh_baseline_governance,
    check_baseline_keys,
    validate_reports,
    validate_all_reports,
    build_approval_summary,
    build_flow_status,
    refresh_feature_state,
    build_flow_overview,
    build_project_next,
    build_project_console,
    build_workspace_hygiene,
    build_tooling_hygiene,
    refresh_project_state,
    upgrade_design_tests,
    latest_design_file,
    is_strict_enabled,
    next_command_requires_strict,
    resolve_schema_refresh_strategy,
    run_design_gates,
    run_prepare_design_cycle,
    run_design_cycle,
    run_implementation_gates,
    run_approved_implementation_cycle,
    detect_next_flow_step,
    run_continue_flow,
    run_feature_cycle,
    run_continue_project_flow,
    run_project_console_cycle,
    run_project_cycle,
    run_full_flow,
    run_refresh_baseline,
    build_command_handlers,
    install_runtime_command,
    emit_result,
    build_json_payload,
)

from sdd_core.application.pipeline_diagnostics import (
    feature_repair_report,
    feature_doctor_command,
    feature_repair_command,
)


def app_dispatch_command(args: argparse.Namespace, handlers: dict[str, Callable]) -> int:
    return 0
