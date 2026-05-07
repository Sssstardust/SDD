#!/usr/bin/env python3
"""
bootstrap_utils.py

Greenfield Bootstrap 产物的公共常量与渲染辅助函数。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BOOTSTRAP_TEMPLATE_DIR = ROOT / ".spec" / "templates" / "bootstrap"
BOOTSTRAP_TEMPLATE_MAP = {
    "constitution.template.md": "constitution.md",
    "architecture.template.md": "architecture.md",
    "module-layout.template.md": "module-layout.md",
    "bootstrap-plan.template.md": "bootstrap-plan.md",
}
BOOTSTRAP_REQUIRED_FILES = tuple(BOOTSTRAP_TEMPLATE_MAP.values())
BOOTSTRAP_REPORT_NAME = "scaffold-report.json"
EXPECTED_SCAFFOLD_ITEMS = (
    "src/main/java",
    "src/test/java",
    "src/main/resources",
    "config",
    "monitoring",
)


def sanitize_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return slug or "feature"


def package_base_for(feature_name: str) -> str:
    return f"com.example.{sanitize_slug(feature_name)}"


def replace_blank_bullet(text: str, label: str, value: str) -> str:
    pattern = rf"(?m)^- {re.escape(label)}[：:]\s*$"
    return re.sub(pattern, f"- {label}： {value}", text)


def replace_table_placeholder(text: str, replacement: str) -> str:
    return text.replace("|  |  |  |  |", replacement, 1)


def render_constitution(template_text: str, feature_name: str) -> str:
    defaults = {
        "命名规范": f"围绕 {feature_name} 业务语义命名，禁止无含义缩写和跨层混用术语",
        "复杂度约束": "单个方法优先保持在 50 行以内，复杂流程必须拆成清晰的小步骤",
        "注释与文档要求": "关键架构决策、边界约束和异常路径必须有中文说明",
        "单元测试要求": "核心领域逻辑必须有可重复执行的单元测试覆盖",
        "集成测试要求": "接口、数据库和关键集成链路必须保留至少一条冒烟验证路径",
        "覆盖率目标": "P0/P1 需求必须可追溯到测试，关键主流程保持可验证",
        "响应时间目标": "同步接口 P95 响应时间默认目标不高于 500ms",
        "容量目标": "上线前明确单实例容量边界和扩容触发条件",
        "资源约束": "禁止在主流程引入不可控的大对象加载和阻塞式批处理",
        "鉴权要求": "所有写操作和敏感查询都必须经过显式鉴权",
        "脱敏要求": "日志、导出和监控中不得直接暴露敏感字段",
        "审计要求": "关键状态流转和配置变更必须具备审计记录",
        "哪些原则属于硬阻断": "分层越界、缺少测试、无鉴权和无回滚方案属于硬阻断",
        "哪些原则允许人工豁免": "性能目标和容量阈值允许在评审记录中说明后临时豁免",
    }
    content = template_text
    for label, value in defaults.items():
        content = replace_blank_bullet(content, label, value)
    return content


def render_architecture(template_text: str, feature_name: str) -> str:
    package_base = package_base_for(feature_name)
    defaults = {
        "feature_name": feature_name,
        "owner": "TBD",
        "系统形态（单体 / 微服务）": "单体内独立业务模块，后续按边界保留拆分空间",
        "主要模块": f"{feature_name}-api、{feature_name}-domain、{feature_name}-infra",
        "关键依赖": "日志、配置、监控、数据库访问、测试框架",
        "接口层": f"{package_base}.controller",
        "应用层": f"{package_base}.service",
        "领域层": f"{package_base}.domain",
        "基础设施层": f"{package_base}.repository / {package_base}.config",
        "事务边界": "仅在应用层聚合写操作时开启事务，避免跨层滥用事务",
        "异常处理": "统一业务异常编码和兜底异常转换，禁止向上抛出裸异常",
        "配置策略": "环境差异通过配置项显式管理，默认值必须可追踪",
        "监控与日志": "主流程指标、错误指标、关键审计日志在 bootstrap 阶段先定义占位",
        "架构边界是否清晰": "当前按四层边界拆分，后续功能设计不得跨层直连",
        "是否存在过早复杂化": "暂不引入额外中间件和多余模块，优先保持可演进的最小骨架",
    }
    content = template_text
    for label, value in defaults.items():
        content = replace_blank_bullet(content, label, value)
    return content


def render_module_layout(template_text: str, feature_name: str) -> str:
    package_base = package_base_for(feature_name)
    content = replace_table_placeholder(
        template_text,
        f"| {feature_name} | 承载 {feature_name} 的核心业务能力与对外接口 | 是 | greenfield bootstrap 默认主模块 |",
    )
    defaults = {
        "controller": f"{package_base}.controller",
        "service": f"{package_base}.service",
        "domain": f"{package_base}.domain",
        "repository": f"{package_base}.repository",
        "config": f"{package_base}.config",
        "允许的依赖方向": "controller -> service -> domain -> repository，config 仅提供基础设施装配",
        "禁止的依赖方向": "repository 反向依赖 service / controller，controller 直接访问 repository",
        "模块划分是否过细": "当前保持单主模块，后续按明确业务边界再拆分子模块",
        "包结构是否便于后续扩展": "预留 controller/service/domain/repository/config 五类基础包结构",
    }
    for label, value in defaults.items():
        content = replace_blank_bullet(content, label, value)
    return content


def render_bootstrap_plan(template_text: str, feature_name: str) -> str:
    content = replace_table_placeholder(
        template_text,
        "| 初始化工程骨架 | 建立基础目录、包结构和配置位 | P0 | bootstrap 自动生成默认规划 |",
    )
    defaults = {
        "本阶段需要完成什么": f"为 {feature_name} 建立可继续进入 Feature Brief / Design 的基础工程约束和脚手架规划",
        "日志": "统一接入结构化日志与关键操作日志字段规范",
        "配置中心": "预留环境化配置装配方式与关键开关位",
        "数据源": "明确主数据源接入方式和迁移脚本目录约定",
        "测试框架": "预留单元测试与集成测试目录，并约定执行入口",
        "监控与告警": "定义主流程指标、错误指标和告警规则占位",
        "初始化阶段风险": "模块边界不清或脚手架缺失会导致后续设计漂移",
        "外部依赖": "数据库、配置、日志、监控等基础设施方案需在实现前确认",
        "是否缺少关键基础设施": "日志、配置、测试、监控和回滚路径都已纳入 bootstrap 规划",
        "是否存在后置成本过高的决定": "暂未发现，当前保持最小可演进骨架",
    }
    for label, value in defaults.items():
        content = replace_blank_bullet(content, label, value)
    return content


def render_bootstrap_file(target_name: str, template_text: str, feature_name: str) -> str:
    if target_name == "constitution.md":
        return render_constitution(template_text, feature_name)
    if target_name == "architecture.md":
        return render_architecture(template_text, feature_name)
    if target_name == "module-layout.md":
        return render_module_layout(template_text, feature_name)
    if target_name == "bootstrap-plan.md":
        return render_bootstrap_plan(template_text, feature_name)
    return template_text


def build_scaffold_report(feature_name: str, generated_files: list[str], preserved_files: list[str]) -> dict[str, object]:
    return {
        "feature_name": feature_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": "PASS",
        "package_base": package_base_for(feature_name),
        "generated_files": generated_files,
        "preserved_files": preserved_files,
        "planned_scaffold": [
            {
                "name": name,
                "status": "PLANNED",
                "purpose": f"{feature_name} bootstrap 默认脚手架项",
            }
            for name in EXPECTED_SCAFFOLD_ITEMS
        ],
    }


def scaffold_report_path(feature_dir: Path) -> Path:
    return feature_dir / BOOTSTRAP_REPORT_NAME


def write_scaffold_report(feature_dir: Path, feature_name: str, generated_files: list[str], preserved_files: list[str]) -> Path:
    report_path = scaffold_report_path(feature_dir)
    report_path.write_text(
        json.dumps(
            build_scaffold_report(feature_name, generated_files, preserved_files),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return report_path
