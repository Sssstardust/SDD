#!/usr/bin/env python3
"""语言无关扫描的 Python 侧适配契约（语言画像注册表）。

背景：阶段三在扫描器接口层引入了 `Entity` / `ScannerAdapter`（语言无关契约），
但 Python 侧的默认扫描根仍硬编码为 Java（src/main/java、src/test/java）。
本模块把「语言 -> 扫描根 / 源码扩展名 / 实体识别正则」收敛为单一注册表，
使附着项目可声明 `language`，从而支持 Java / Python / TypeScript 等多语言扫描。

设计取舍：
- 仅提供「画像」（语言相关的路径与模式约定），不绑定任何具体扫描器实现，
  因此对 MCP 侧（project-explorer）与 Python 侧脚本都可复用。
- 未知语言回退到通用画像（以项目根作为扫描根），保证不报错、不丢能力。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LanguageProfile:
    """单一语言的扫描画像。

    language: 规范化语言标识（小写）。
    scan_roots: 相对项目根的源码扫描根（按优先级）。
    schema_roots: 相对项目根的 Schema / 资源根。
    source_extensions: 用于识别源码文件的扩展名。
    entity_patterns: 用于启发式识别实体（类/函数/模块）的正则片段。
    """

    language: str
    scan_roots: tuple[str, ...]
    schema_roots: tuple[str, ...]
    source_extensions: tuple[str, ...]
    entity_patterns: tuple[str, ...] = field(default_factory=tuple)


# 单一真相源：语言画像注册表。
LANGUAGE_PROFILES: dict[str, LanguageProfile] = {
    "java": LanguageProfile(
        language="java",
        scan_roots=("src/main/java", "src/test/java"),
        schema_roots=("src/main/resources", "src/test/resources", "db", "sql"),
        source_extensions=(".java",),
        entity_patterns=(r"\b(?:public|private|protected)?\s*(?:class|interface|enum)\s+(\w+)",),
    ),
    "python": LanguageProfile(
        language="python",
        scan_roots=("src", "."),
        schema_roots=("db", "sql", "migrations", "alembic"),
        source_extensions=(".py",),
        entity_patterns=(r"^\s*class\s+(\w+)", r"^\s*def\s+(\w+)"),
    ),
    "typescript": LanguageProfile(
        language="typescript",
        scan_roots=("src",),
        schema_roots=("db", "sql", "prisma", "migrations"),
        source_extensions=(".ts", ".tsx"),
        entity_patterns=(
            r"\b(?:export\s+)?(?:class|interface|enum)\s+(\w+)",
            r"\b(?:export\s+)?(?:function)\s+(\w+)",
        ),
    ),
}

# 别名归一化（接受常见写法）。
_LANGUAGE_ALIASES = {
    "ts": "typescript",
    "tsx": "typescript",
    "node": "typescript",
    "py": "python",
    "py3": "python",
    "jvm": "java",
}

DEFAULT_LANGUAGE = "java"

# 通用回退画像：未知语言时以项目根为扫描根，避免丢失能力。
GENERIC_PROFILE = LanguageProfile(
    language="generic",
    scan_roots=(".",),
    schema_roots=("db", "sql"),
    source_extensions=(),
    entity_patterns=(),
)


def normalize_language(value: str | None) -> str:
    """把语言标识归一化为注册表 key；空值回退默认语言。"""
    if not value:
        return DEFAULT_LANGUAGE
    key = str(value).strip().lower()
    return _LANGUAGE_ALIASES.get(key, key)


def get_language_profile(language: str | None) -> LanguageProfile:
    """返回语言画像；未知语言回退通用画像。"""
    return LANGUAGE_PROFILES.get(normalize_language(language), GENERIC_PROFILE)


def supported_languages() -> list[str]:
    return sorted(LANGUAGE_PROFILES)
