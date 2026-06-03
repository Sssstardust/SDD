#!/usr/bin/env python3
"""
SDD Semantic Action: Design (Requirements -> Technical Solution)
"""

import sys
import subprocess
from pathlib import Path
from typing import Any
import argparse

from .pipeline_execution import run_steps

def console_print(message: str) -> None:
    print(message)

from infrastructure.versioning import resolve_feature_dir

def run_design(args: argparse.Namespace) -> int:
    """语义命令：架构设计生成 (Structured JSON -> Design + Design Pack)"""
    feature_dir = resolve_feature_dir(args.feature_name)
    root = Path(__file__).resolve().parent.parent.parent
    
    def step_init_design():
        script = root / "scripts" / "init_design.py"
        return subprocess.run([sys.executable, str(script), feature_dir]).returncode

    def step_generate_design():
        # 这里需要调用 scripts/run_pipeline.py 中的逻辑，但目前是通过直接调用 generator 实现
        # 为了完美解耦，我们应直接运行命令
        # 目前暂时使用 subprocess 调用 run_pipeline 的原子命令
        cmd = [sys.executable, str(root / "scripts" / "run_pipeline.py"), "generate-design", feature_dir]
        if args.force:
            cmd.append("--force")
        return subprocess.run(cmd).returncode

    def step_init_pack():
        script = root / "scripts" / "init_design_pack.py"
        brief_path = str(Path(feature_dir) / "需求规格.md")
        return subprocess.run([sys.executable, str(script), brief_path]).returncode

    steps = [
        ("init-design", step_init_design),
        ("generate-design", step_generate_design),
        ("init-design-pack", step_init_pack)
    ]
    return run_steps(steps, console_print=console_print)
