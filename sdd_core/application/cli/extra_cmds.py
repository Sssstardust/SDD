import argparse
from sdd_core.application.cli.core import registry

from sdd_core.application.pipeline_facade import (
    build_flow_status, run_feature_cycle, build_flow_overview,
    build_project_next, build_project_console, run_project_console_cycle,
    run_continue_project_flow, run_project_cycle, build_tooling_hygiene,
    build_workspace_hygiene, upgrade_design_tests, run_prepare_design_cycle,
    run_design_cycle, run_design_gates, run_implementation_gates, run_full_flow,
    install_runtime_command, feature_doctor_command, feature_repair_command
)

@registry.register("flow-status")
def setup_flow_status(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: build_flow_status(
        args.feature_dir, getattr(args, "attachment_file", None), getattr(args, "profile", None)
    ))

@registry.register("feature-cycle")
def setup_feature_cycle(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.set_defaults(func=lambda args: run_feature_cycle(args.feature_dir))

@registry.register("flow-overview")
def setup_flow_overview(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: build_flow_overview(
        getattr(args, "attachment_file", None), getattr(args, "profile", None)
    ))

@registry.register("project-next")
def setup_project_next(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: build_project_next(
        getattr(args, "attachment_file", None), getattr(args, "profile", None)
    ))

@registry.register("project-console")
def setup_project_console(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: build_project_console(
        getattr(args, "attachment_file", None), getattr(args, "profile", None)
    ))

@registry.register("project-console-cycle")
def setup_project_console_cycle(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: run_project_console_cycle(
        getattr(args, "attachment_file", None), getattr(args, "profile", None)
    ))

@registry.register("continue-project-flow")
def setup_continue_project_flow(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: run_continue_project_flow(
        getattr(args, "attachment_file", None), getattr(args, "profile", None)
    ))

@registry.register("project-cycle")
def setup_project_cycle(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: run_project_cycle(
        getattr(args, "attachment_file", None), getattr(args, "profile", None)
    ))

@registry.register("tooling-hygiene")
def setup_tooling_hygiene(parser: argparse.ArgumentParser) -> None:
    parser.set_defaults(func=lambda args: build_tooling_hygiene())

@registry.register("workspace-hygiene")
def setup_workspace_hygiene(parser: argparse.ArgumentParser) -> None:
    parser.set_defaults(func=lambda args: build_workspace_hygiene())

@registry.register("upgrade-design-tests")
def setup_upgrade_design_tests(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--feature", help="仅升级指定 feature")
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: upgrade_design_tests(
        getattr(args, "feature", None), getattr(args, "attachment_file", None), getattr(args, "profile", None)
    ))

@registry.register("prepare-design-cycle")
def setup_prepare_design_cycle(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: run_prepare_design_cycle(
        args.feature_dir, getattr(args, "attachment_file", None), getattr(args, "profile", None)
    ))

@registry.register("design-cycle")
def setup_design_cycle(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--strict", action="store_true", help="严格模式")
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: run_design_cycle(
        args.feature_dir, args.strict, getattr(args, "attachment_file", None), getattr(args, "profile", None)
    ))

@registry.register("design-gates")
def setup_design_gates(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--strict", action="store_true", help="严格模式")
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: run_design_gates(
        args.feature_dir, args.strict, getattr(args, "attachment_file", None), getattr(args, "profile", None)
    ))

@registry.register("implementation-gates")
def setup_implementation_gates(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--strict", action="store_true", help="严格模式")
    parser.set_defaults(func=lambda args: run_implementation_gates(args.feature_dir, args.strict))

@registry.register("full-flow")
def setup_full_flow(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--strict", action="store_true", help="严格模式")
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: run_full_flow(
        args.feature_dir, args.strict, getattr(args, "attachment_file", None), getattr(args, "profile", None)
    ))

@registry.register("install-runtime")
def setup_install_runtime(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("target_root", help="目标项目根目录")
    parser.add_argument("--runtime-dir", default=".sdd", help="运行时安装目录名称")
    parser.add_argument("--force", action="store_true", help="强制重新安装")
    parser.set_defaults(func=lambda args: install_runtime_command(
        args.target_root, args.runtime_dir, getattr(args, "force", False)
    ))

@registry.register("feature-doctor")
def setup_feature_doctor(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: feature_doctor_command(
        args.feature_dir, getattr(args, "attachment_file", None), getattr(args, "profile", None)
    ))

@registry.register("feature-repair")
def setup_feature_repair(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: feature_repair_command(
        args.feature_dir, getattr(args, "attachment_file", None), getattr(args, "profile", None)
    ))
