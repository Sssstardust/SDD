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

from sdd_core.infrastructure.concurrency import atomic_write_text
from sdd_core.infrastructure.baseline_paths import get_active_spec_dir


ROOT = Path(__file__).resolve().parents[3]


def _bootstrap_template_dir() -> Path:
    return get_active_spec_dir(root=ROOT) / "templates" / "bootstrap"
BOOTSTRAP_TEMPLATE_MAP = {
    "README.template.md": "README.md",
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


def render_feature_readme(template_text: str, feature_name: str) -> str:
    package_base = package_base_for(feature_name)
    replacements = {
        "{{feature_name}}": feature_name,
        "{{package_base}}": package_base,
    }
    content = template_text
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    return content


def render_bootstrap_file(target_name: str, template_text: str, feature_name: str) -> str:
    if target_name == "README.md":
        return render_feature_readme(template_text, feature_name)
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
    return feature_dir / ".generated" / BOOTSTRAP_REPORT_NAME


def write_scaffold_report(feature_dir: Path, feature_name: str, generated_files: list[str], preserved_files: list[str]) -> Path:
    report_path = scaffold_report_path(feature_dir)
    atomic_write_text(
        report_path,
        json.dumps(
            build_scaffold_report(feature_name, generated_files, preserved_files),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return report_path
