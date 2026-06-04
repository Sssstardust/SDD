#!/usr/bin/env python3
"""
SDD Semantic Action: Validate (Design -> Architecture Audit)
"""

import sys
import subprocess
from pathlib import Path
from typing import Any
import argparse

from .pipeline_execution import run_steps

def console_print(message: str) -> None:
    print(message)

from sdd_core.infrastructure.versioning import resolve_feature_dir

def run_validate(args: argparse.Namespace) -> int:
    """语义命令：多维设计校验 (Gate 1/2/3 联合校验)"""
    feature_dir = resolve_feature_dir(args.feature_name)
    root = Path(__file__).resolve().parent.parent.parent
    
    def step_gate1():
        script = root / "sdd_core" / "gate1.py"
        return subprocess.run([sys.executable, str(script), feature_dir]).returncode

    def step_gate2():
        script = root / "sdd_core" / "check_design_truthfulness.py"
        cmd = [sys.executable, str(script), feature_dir]
        if args.strict:
            cmd.append("--strict")
        return subprocess.run(cmd).returncode

    def step_gate3():
        script = root / "sdd_core" / "check_arch_semantics.py"
        return subprocess.run([sys.executable, str(script), feature_dir]).returncode

    steps = [
        ("gate1", step_gate1),
        ("gate2", step_gate2),
        ("gate3", step_gate3)
    ]
    return run_steps(steps, console_print=console_print)
