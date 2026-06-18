#!/usr/bin/env python3
"""SDD semantic validate action."""

from __future__ import annotations

import argparse

from sdd_core.application.gates.gate_runtime import run_gate1, run_gate2, run_gate3
from sdd_core.application.pipeline_execution import run_steps
from sdd_core.infrastructure.versioning import resolve_feature_dir


def console_print(message: str) -> None:
    print(message)


def run_validate(args: argparse.Namespace) -> int:
    """Run Gate 1/2/3 design validation as one semantic command."""
    feature_dir = resolve_feature_dir(args.feature_name)
    steps = [
        ("gate1", lambda: run_gate1(feature_dir)),
        ("gate2", lambda: run_gate2(feature_dir, strict=args.strict)),
        ("gate3", lambda: run_gate3(feature_dir)),
    ]
    return run_steps(steps, console_print=console_print)
