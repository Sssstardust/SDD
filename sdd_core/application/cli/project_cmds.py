import argparse
from sdd_core.application.cli.core import registry

# 导入业务方法
from sdd_core.application.pipeline_facade import (
    sync_baseline, refresh_module_map, attach_project, onboard_project,
    refresh_schema_context, refresh_baseline_governance,
    run_refresh_baseline, refresh_project_state, check_arch_standards_sync
)

@registry.register("sync-baseline")
def setup_sync_baseline(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--design-version", help="指定同步的设计版本")
    parser.set_defaults(func=lambda args: sync_baseline(args.feature_dir, getattr(args, "design_version", None)))

@registry.register("refresh-module-map")
def setup_refresh_module_map(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: refresh_module_map(
        getattr(args, "attachment_file", None), getattr(args, "profile", None)
    ))

@registry.register("attach-project")
def setup_attach_project(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("project_root", nargs="?", help="目标项目根目录")
    parser.add_argument("--name", help="项目名称")
    parser.add_argument("--clear", action="store_true", help="清除现有配置")
    parser.add_argument("--design-root", action="append", help="设计根目录")
    parser.add_argument("--schema-root", action="append", help="Schema 根目录")
    parser.add_argument("--components-file", help="组件定义文件")
    parser.add_argument("--profile", help="配置 Profile")
    parser.add_argument("--project-id", help="显式指定项目 ID")
    parser.add_argument("--list-profiles", action="store_true", help="列出所有 Profile")
    parser.add_argument("--activate-profile", help="激活指定 Profile")
    parser.add_argument("--attachment-file", default=None)
    parser.set_defaults(func=lambda args: attach_project(
        args.project_root, show=False, clear=args.clear, name=args.name,
        design_roots=args.design_root, schema_roots=args.schema_root,
        components_file=args.components_file, profile=args.profile,
        project_id=args.project_id, list_profiles=args.list_profiles,
        activate_profile=args.activate_profile,
        attachment_file=getattr(args, "attachment_file", None)
    ))

@registry.register("show-attachment")
def setup_show_attachment(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: attach_project(show=True, profile=getattr(args, "profile", None)))

@registry.register("onboard-project")
def setup_onboard_project(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("project_root", nargs="?", help="目标项目根目录")
    parser.add_argument("--name", help="项目名称")
    parser.add_argument("--design-root", action="append", help="设计根目录")
    parser.add_argument("--schema-root", action="append", help="Schema 根目录")
    parser.add_argument("--components-file", help="组件定义文件")
    parser.add_argument("--profile", help="配置 Profile")
    parser.add_argument("--project-id", help="显式指定项目 ID")
    parser.add_argument("--attachment-file", default=None)
    parser.set_defaults(func=lambda args: onboard_project(
        args.project_root, name=args.name, design_roots=args.design_root,
        schema_roots=args.schema_root, components_file=args.components_file,
        profile=args.profile, project_id=args.project_id,
        attachment_file=getattr(args, "attachment_file", None)
    ))

@registry.register("bootstrap-attached-project")
def setup_bootstrap_attached_project(parser: argparse.ArgumentParser) -> None:
    # 与 onboard-project 逻辑一致
    setup_onboard_project(parser)

@registry.register("refresh-schema-context")
def setup_refresh_schema_context(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--from-polyquery", action="store_true", help="使用 PolyQuery 获取真实数据库 schema")
    parser.add_argument("--polyquery-config", help="显式指定 polyquery 配置路径")
    parser.add_argument("--polyquery-snapshot", help="直接使用已存在的 schema snapshot json (跳过查询)")
    parser.add_argument("--auto-discover", help="自动发现指定 feature 所需的表并生成配置 (传入 feature 目录)")
    parser.add_argument("--polyquery-fallback", choices=["local", "fail"], default="local", help="当 polyquery 不可用时的回退策略 (local=退回解析本地sql, fail=直接报错)")
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: refresh_schema_context(
        from_polyquery=args.from_polyquery, polyquery_config=args.polyquery_config,
        polyquery_snapshot=args.polyquery_snapshot, auto_discover=args.auto_discover,
        polyquery_fallback=args.polyquery_fallback,
        attachment_file=getattr(args, "attachment_file", None), profile=getattr(args, "profile", None)
    ))

@registry.register("refresh-baseline-governance")
def setup_refresh_baseline_governance(parser: argparse.ArgumentParser) -> None:
    parser.set_defaults(func=lambda args: refresh_baseline_governance())

@registry.register("refresh-baseline")
def setup_refresh_baseline(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("feature_dir", nargs="?", help="specs/<feature> 目录路径 (可选)")
    parser.add_argument("--strict", action="store_true", help="严格模式 (所有阶段必须成功)")
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: run_refresh_baseline(
        strict=getattr(args, "strict", False), feature_dir=getattr(args, "feature_dir", None),
        attachment_file=getattr(args, "attachment_file", None), profile=getattr(args, "profile", None)
    ))

@registry.register("refresh-project-state")
def setup_refresh_project_state(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--feature", help="单独刷新指定特性")
    parser.add_argument("--attachment-file", default=None)
    parser.add_argument("--profile", default=None)
    parser.set_defaults(func=lambda args: refresh_project_state(
        getattr(args, "feature", None), getattr(args, "attachment_file", None), getattr(args, "profile", None)
    ))

@registry.register("check-arch-standards-sync")
def setup_check_arch_standards_sync(parser: argparse.ArgumentParser) -> None:
    parser.set_defaults(func=lambda args: check_arch_standards_sync())
