import argparse
from sdd_core.application.cli.core import registry

# 导入真实业务方法
from sdd_core.application.semantic_design import run_design as run_semantic_design
from sdd_core.application.pipeline_facade import (
    init_design, generate_design, check_design,
    init_design_pack, check_design_pack,
    cancel_design, archive_design, update_design_index
)

@registry.register("design", help="[SEMANTIC] 架构设计生成 (Structured JSON -> Design MD + Pack)")
def setup_design(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_name", help="feature 名称或 specs/<feature> 路径")
    parser.add_argument("--force", action="store_true", help="允许覆盖当前设计版本与 design-pack")
    parser.set_defaults(func=lambda args: run_semantic_design(
        feature_name=args.feature_name,
        force=args.force
    ))

@registry.register("init-design")
def setup_init_design(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.set_defaults(func=lambda args: init_design(args.feature_dir))

@registry.register("generate-design")
def setup_generate_design(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--feedback", help="AI 反馈建议文本")
    parser.add_argument("--force", action="store_true", help="允许覆盖已存在的设计文档")
    parser.add_argument("--resume", action="store_true", help="在现有设计基础上续写")
    parser.set_defaults(func=lambda args: generate_design(
        args.feature_dir, args.feedback, args.force, args.resume
    ))

@registry.register("check-design")
def setup_check_design(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("design_file", help="技术方案.md 路径")
    parser.set_defaults(func=lambda args: check_design(args.design_file))

@registry.register("init-design-pack")
def setup_init_design_pack(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_brief", help="需求规格.md 路径")
    parser.set_defaults(func=lambda args: init_design_pack(args.feature_brief))

@registry.register("check-design-pack")
def setup_check_design_pack(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_brief", help="需求规格.md 路径")
    parser.set_defaults(func=lambda args: check_design_pack(args.feature_brief))

@registry.register("cancel-design")
def setup_cancel_design(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--reason", help="取消原因")
    parser.set_defaults(func=lambda args: cancel_design(args.feature_dir, args.reason))

@registry.register("archive-design")
def setup_archive_design(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_name", help="feature 名称")
    parser.add_argument("--intent-id", help="特定 intent ID")
    parser.add_argument("--status", help="目标状态")
    parser.add_argument("--reason", help="归档原因")
    parser.set_defaults(func=lambda args: archive_design(
        args.feature_name, args.intent_id, args.status, args.reason
    ))

@registry.register("update-design-index")
def setup_update_design_index(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: update_design_index(args.feature_dir))
