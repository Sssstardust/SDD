import argparse
from sdd_core.application.cli.core import registry

# 从原本 run_pipeline.py 导入业务方法
from sdd_core.application.semantic_analyze import run_analyze as run_semantic_analyze
from sdd_core.application.pipeline_facade import generate_feature_brief, init_feature, bootstrap

@registry.register("analyze", help="[SEMANTIC] PRD 分析与结构化 (PRD -> Structured JSON)")
def setup_analyze(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("source_file", help="PRD/需求文本文件路径")
    parser.add_argument("feature_name", help="feature 名称或 specs/<feature> 路径")
    parser.add_argument("--force", action="store_true", help="允许覆盖已存在的 需求规格.md")
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: run_semantic_analyze(
        source_file=args.source_file,
        feature_name=args.feature_name,
        force=args.force,
        attachment_file=args.attachment_file,
        profile=args.profile
    ))

@registry.register("generate-feature-brief")
def setup_generate_feature_brief(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("source_file", help="PRD/需求文本文件路径")
    parser.add_argument("feature_name", help="feature 名称或 specs/<feature> 路径")
    parser.add_argument("--force", action="store_true", help="允许覆盖已存在的 需求规格.md")
    parser.add_argument("--attachment-file", default=None, help="attachment config path")
    parser.add_argument("--profile", default=None, help="attachment profile name")
    parser.set_defaults(func=lambda args: generate_feature_brief(
        source_file=args.source_file,
        feature_name=args.feature_name,
        force=args.force,
        attachment_file=args.attachment_file,
        profile=args.profile
    ))

@registry.register("init-feature")
def setup_init_feature(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_name", help="feature 名称")
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: init_feature(
        feature_name=args.feature_name,
        attachment_file=args.attachment_file,
        profile=args.profile
    ))

@registry.register("bootstrap")
def setup_bootstrap(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--force", action="store_true", help="允许覆盖已存在的 bootstrap 产物")
    parser.set_defaults(func=lambda args: bootstrap(
        feature_dir=args.feature_dir,
        force=args.force
    ))

@registry.register("greenfield-init")
def setup_greenfield_init(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--force", action="store_true", help="允许覆盖已存在的 bootstrap 产物")
    # run_pipeline 没有直接定义 greenfield_init 的处理，实际是通过 dispatch_command 调用 bootstrap 或者外部。
    # 这里我们映射到 bootstrap，原分发逻辑一致。
    parser.set_defaults(func=lambda args: bootstrap(
        feature_dir=args.feature_dir,
        force=args.force
    ))

@registry.register("scaffold")
def setup_scaffold(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    # 原 run_pipeline.py 也没有定义 scaffold 的独立 python handler，它是一个由 run_pipeline CLI 触发并在 application 层被特殊处理的。
    # 根据原有 dispatch_command，如果有对应的处理则映射
    from sdd_core.application.pipeline_facade import run_external_command
    import sys
    from pathlib import Path
    parser.set_defaults(func=lambda args: run_external_command([sys.executable, str(Path(__file__).resolve().parent.parent.parent / "sdd_core" / "generate_test_skeleton.py"), args.feature_dir]))

