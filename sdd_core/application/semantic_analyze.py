#!/usr/bin/env python3
"""
SDD Semantic Action: Analyze (PRD -> Structured Requirements)
"""

from pathlib import Path
from typing import Optional
import argparse

from .pipeline_execution import run_steps
from sdd_core.infrastructure.versioning import resolve_feature_dir, DEFAULT_ATTACHMENT_PATH

# 注入打印函数
def console_print(message: str) -> None:
    print(message)


from sdd_core.application.generators.generate_feature_brief import run_generate_feature_brief

def run_analyze(
    source_file: str,
    feature_name: str,
    force: bool = False,
    attachment_file: Optional[str] = None,
    profile: Optional[str] = None,
) -> int:
    """语义命令：需求分析与结构化校验 (PRD -> Structured JSON)"""
    attachment_path = Path(attachment_file) if attachment_file else DEFAULT_ATTACHMENT_PATH
    feature_dir = resolve_feature_dir(feature_name, attachment_path=attachment_path, profile=profile)
    feature_brief = Path(feature_dir) / "需求规格.md"
    
    def step_generate_brief():
        return run_generate_feature_brief(
            source_file=source_file,
            feature_name=feature_name,
            force=force,
            attachment_file=attachment_file,
            profile=profile
        )

    def step_verify_brief():
        # 简单校验文件是否存在，后续可调用 gate1_checker 的深度校验
        exists = feature_brief.exists()
        if not exists:
            console_print(f"[ERROR] feature-brief generation failed: {feature_brief}")
            return 1
        console_print(f"[OK] feature-brief verified: {feature_brief}")
        return 0

    steps = [
        ("generate-feature-brief", step_generate_brief),
        ("verify-brief", step_verify_brief)
    ]
    return run_steps(steps, console_print=console_print)


def run_analyze_cli(args: argparse.Namespace) -> int:
    """CLI 包装层"""
    return run_analyze(
        source_file=args.source_file,
        feature_name=args.feature_name,
        force=args.force,
        attachment_file=getattr(args, "attachment_file", None),
        profile=getattr(args, "profile", None),
    )

