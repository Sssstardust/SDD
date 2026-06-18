#!/usr/bin/env python3
"""
generate_feature_brief.py

根据 PRD / 需求文本生成第一版 需求规格.md。
当前版本采用启发式规则，不依赖模型调用。
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from sdd_core.infrastructure.concurrency import atomic_write_text, feature_lock
from sdd_core.infrastructure.versioning import resolve_feature_dir, DEFAULT_ATTACHMENT_PATH
from sdd_core.domain.requirement_heuristics import (
    has_greenfield_signal,
    infer_capability_tags,
    infer_feature_type,
    infer_risk_tier,
)
from sdd_core.domain.requirement_parser import (
    first_heading_or_line,
    extract_requirements,
    build_one_liner,
)
from sdd_core.application.generators.feature_brief_renderer import render_feature_brief

ROOT = Path(__file__).resolve().parent.parent.parent

def read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def detect_project_mode(text: str) -> tuple[str, list[str], float]:
    if has_greenfield_signal(text):
        return "greenfield", [f"需求文本命中 greenfield 信号"], 0.85

    evidence: list[str] = []
    if (ROOT / "src" / "main" / "java").exists():
        evidence.append("检测到现有 src/main/java")
    if (ROOT / "specs").exists():
        evidence.append("检测到已有 feature 试点目录")
    if not evidence:
        evidence.append("未命中 greenfield 信号，默认按 brownfield 处理")
    return "brownfield", evidence, 0.80

def run_generate_feature_brief(
    source_file: str,
    feature_name: str,
    force: bool = False,
    attachment_file: Optional[str] = None,
    profile: Optional[str] = None,
) -> int:
    """核心逻辑函数：生成需求规格说明书"""
    source_path = Path(source_file)
    if not source_path.exists():
        print(f"[ERROR] 源文件不存在: {source_path}")
        return 1

    eff_attachment = Path(attachment_file) if attachment_file else DEFAULT_ATTACHMENT_PATH
    
    feature_dir = resolve_feature_dir(feature_name, attachment_path=eff_attachment, profile=profile)
    feature_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = feature_dir / "需求规格.md"
    if output_path.exists() and not force:
        print(f"[ERROR] feature-brief 已存在，若需覆盖请使用 --force: {output_path}")
        return 1

    source_text = read_source(source_path)
    detected_title = first_heading_or_line(source_text)
    feature_name_eff = feature_dir.name
    project_mode, evidence, confidence = detect_project_mode(source_text)
    
    tags = infer_capability_tags(source_text)
    risk_tier = infer_risk_tier(set(tags))
    feature_type = infer_feature_type(detected_title, source_text, set(tags))
    
    requirements = extract_requirements(source_text)
    one_liner = build_one_liner(detected_title, requirements)

    rendered = render_feature_brief(
        project_mode=project_mode,
        project_mode_evidence=evidence,
        project_mode_confidence=confidence,
        feature_name=feature_name_eff,
        feature_type=feature_type,
        one_liner=one_liner,
        tags=tags,
        risk_tier=risk_tier,
        requirements=requirements,
        source_path=source_path,
    )
    with feature_lock(feature_dir, phase="generate-feature-brief"):
        atomic_write_text(output_path, rendered, encoding="utf-8")

    print("[OK] Feature Brief 自动生成完成")
    print(f"  - source:  {source_path}")
    print(f"  - feature: {feature_name_eff}")
    print(f"  - output:  {output_path}")
    return 0

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_file", help="PRD/需求文本文件路径")
    parser.add_argument("feature_name", help="feature 名称或 specs/<feature> 路径")
    parser.add_argument("--force", action="store_true", help="允许覆盖已存在的 需求规格.md")
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    args = parser.parse_args()

    return run_generate_feature_brief(
        source_file=args.source_file,
        feature_name=args.feature_name,
        force=args.force,
        attachment_file=args.attachment_file,
        profile=args.profile,
    )

if __name__ == "__main__":
    raise SystemExit(main())
