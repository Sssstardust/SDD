import argparse
from sdd_core.application.cli.core import registry

# 导入业务方法
from sdd_core.application.semantic_validate import run_validate as run_semantic_validate
from sdd_core.application.pipeline_facade import (
    gate1, gate2, gate3, gate4, gate5,
    release_gate, init_approval, approve_design, check_approval,
    validate_reports, validate_all_reports, build_approval_summary,
    generate_task_slices
)

@registry.register("validate", help="[SEMANTIC] 多维设计校验 (Gate 1/2/3 联合校验)")
def setup_validate(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_name", help="feature 名称或 specs/<feature> 路径")
    parser.add_argument("--strict", action="store_true", help="启用架构红线严格检查")
    parser.set_defaults(func=lambda args: run_semantic_validate(args))

@registry.register("gate1")
def setup_gate1(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.set_defaults(func=lambda args: gate1(args.feature_dir))

@registry.register("gate2")
def setup_gate2(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--strict", action="store_true", help="严格模式")
    parser.set_defaults(func=lambda args: gate2(args.feature_dir, strict=args.strict))

@registry.register("gate3")
def setup_gate3(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.set_defaults(func=lambda args: gate3(args.feature_dir))

@registry.register("gate4")
def setup_gate4(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.set_defaults(func=lambda args: gate4(args.feature_dir))

@registry.register("gate5")
def setup_gate5(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--require-attached-execution", action="store_true", help="要求附着项目 verification_commands 成功执行")
    parser.add_argument("--strict", action="store_true", help="严格模式")
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: gate5(
        args.feature_dir, args.require_attached_execution, args.strict,
        getattr(args, "attachment_file", None), getattr(args, "profile", None)
    ))

@registry.register("release-gate")
def setup_release_gate(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--strict", action="store_true", help="严格模式")
    parser.set_defaults(func=lambda args: release_gate(args.feature_dir, strict=args.strict))

@registry.register("pre-release-check")
def setup_pre_release_check(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--strict", action="store_true", help="严格模式")
    parser.set_defaults(func=lambda args: release_gate(args.feature_dir, strict=args.strict))

@registry.register("go-live-check")
def setup_go_live_check(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--strict", action="store_true", help="严格模式")
    parser.set_defaults(func=lambda args: release_gate(args.feature_dir, strict=args.strict))

@registry.register("init-approval")
def setup_init_approval(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.set_defaults(func=lambda args: init_approval(args.feature_dir))

@registry.register("approve-design")
def setup_approve_design(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--approved-by", required=True, help="审批人")
    parser.add_argument("--comments", help="审批意见")
    parser.add_argument("--status", choices=["APPROVED", "REJECTED", "PENDING"], default="APPROVED", help="approval status")
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: approve_design(
        args.feature_dir, args.approved_by, args.comments, args.status,
        getattr(args, "attachment_file", None), getattr(args, "profile", None)
    ))

@registry.register("check-approval")
def setup_check_approval(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: check_approval(
        args.feature_dir, getattr(args, "attachment_file", None), getattr(args, "profile", None)
    ))

@registry.register("validate-reports")
def setup_validate_reports(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--stage", default="all")
    parser.set_defaults(func=lambda args: validate_reports(args.feature_dir, getattr(args, "stage", "all")))

@registry.register("validate-all-reports")
def setup_validate_all_reports(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--stage", default="all")
    parser.add_argument("--require-verify", action="store_true")
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: validate_all_reports(
        getattr(args, "stage", "all"), args.require_verify,
        getattr(args, "attachment_file", None), getattr(args, "profile", None)
    ))

@registry.register("build-approval-summary")
def setup_build_approval_summary(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.set_defaults(func=lambda args: build_approval_summary(args.feature_dir))

@registry.register("generate-task-slices")
def setup_generate_task_slices(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--force", action="store_true", help="强制覆盖现有任务切片")
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: generate_task_slices(
        args.feature_dir, getattr(args, "attachment_file", None),
        getattr(args, "profile", None), args.force
    ))
