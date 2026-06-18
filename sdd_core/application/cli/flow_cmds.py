import argparse
from sdd_core.application.cli.core import registry

# 导入业务方法
from sdd_core.application.pipeline_facade import run_approved_implementation_cycle, run_continue_flow

@registry.register("approved-implementation-cycle")
def setup_approved_implementation_cycle(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--strict", action="store_true", help="严格模式")
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: run_approved_implementation_cycle(
        args.feature_dir, args.strict,
        getattr(args, "attachment_file", None), getattr(args, "profile", None)
    ))

@registry.register("continue-flow")
def setup_continue_flow(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.set_defaults(func=lambda args: run_continue_flow(args.feature_dir))
