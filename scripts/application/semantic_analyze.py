#!/usr/bin/env python3
"""
SDD Semantic Action: Analyze (PRD -> Structured Requirements)
"""

import sys
from pathlib import Path
from typing import Any
import argparse

from .pipeline_execution import run_steps

# 注入打印函数
def console_print(message: str) -> None:
    print(message)

from infrastructure.versioning import resolve_feature_dir, DEFAULT_ATTACHMENT_PATH

def run_analyze(args: argparse.Namespace) -> int:
    """语义命令：需求分析与结构化校验 (PRD -> Structured JSON)"""
    attachment_path = Path(args.attachment_file) if args.attachment_file else DEFAULT_ATTACHMENT_PATH
    feature_dir = resolve_feature_dir(args.feature_name, attachment_path=attachment_path, profile=args.profile)
    feature_brief = Path(feature_dir) / "需求规格.md"
    
    # 延迟加载，避免循环依赖，且直接调用原始脚本逻辑
    from generate_feature_brief import render_feature_brief
    from gate1 import verify

    def step_generate_brief():
        # 这里直接模拟 run_pipeline.py 中的逻辑
        # 实际应调用 scripts/generate_feature_brief.py 的核心逻辑
        import subprocess
        root = Path(__file__).resolve().parent.parent.parent
        script = root / "scripts" / "generate_feature_brief.py"
        cmd = [sys.executable, str(script), args.source_file, args.feature_name]
        if args.force:
            cmd.append("--force")
        if args.attachment_file:
            cmd.extend(["--attachment-file", args.attachment_file])
        if args.profile:
            cmd.extend(["--profile", args.profile])
        
        # 使用 subprocess 运行以保持独立性
        result = subprocess.run(cmd)
        return result.returncode

    steps = [
        ("generate-feature-brief", step_generate_brief),
        ("verify-brief", lambda: verify(str(feature_brief)))
    ]
    return run_steps(steps, console_print=console_print)
