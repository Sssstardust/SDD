#!/usr/bin/env python3
"""
SDD Semantic Action: Design (Requirements -> Technical Solution)
"""

import sys
import subprocess
from pathlib import Path
from typing import Any, Optional
import argparse

from .pipeline_execution import run_steps
from sdd_core.infrastructure.versioning import resolve_feature_dir

def console_print(message: str) -> None:
    print(message)


def run_design(
    feature_name: str,
    force: bool = False,
) -> int:
    """语义命令：架构设计生成 (Structured JSON -> Design + Design Pack)"""
    feature_dir = resolve_feature_dir(feature_name)
    root = Path(__file__).resolve().parent.parent.parent
    
    def step_init_design():
        script = root / "sdd_core" / "application" / "generators" / "init_design.py"
        return subprocess.run([sys.executable, str(script), str(feature_dir)]).returncode

    def step_generate_design():
        # 调用 run_pipeline 的子命令
        cmd = [sys.executable, str(root / "sdd_core" / "run_pipeline.py"), "generate-design", str(feature_dir)]
        if force:
            cmd.append("--force")
        return subprocess.run(cmd).returncode

    def step_init_pack():
        script = root / "sdd_core" / "application" / "generators" / "init_design_pack.py"
        brief_path = str(Path(feature_dir) / "需求规格.md")
        return subprocess.run([sys.executable, str(script), brief_path]).returncode

    steps = [
        ("init-design", step_init_design),
        ("generate-design", step_generate_design),
        ("init-design-pack", step_init_pack)
    ]
    return run_steps(steps, console_print=console_print)


def run_design_cli(args: argparse.Namespace) -> int:
    """CLI 包装层"""
    return run_design(
        feature_name=args.feature_name,
        force=args.force
    )

