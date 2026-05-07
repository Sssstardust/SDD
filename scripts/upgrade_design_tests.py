#!/usr/bin/env python3
"""
upgrade_design_tests.py

把已有设计验证测试升级成可直接执行的 Java 类：
- public class
- public test methods
- main() 入口

仅处理正式 feature 对应的 generated/design 目录，不处理 _validation-* 临时目录。
"""

from __future__ import annotations

import argparse
import re

from versioning import iter_feature_dirs

ROOT = Path(__file__).resolve().parent.parent
DESIGN_TEST_ROOT = ROOT / "src" / "test" / "java" / "generated" / "design"


CLASS_DECL_PATTERN = re.compile(r"(?m)^class\s+([A-Z][A-Za-z0-9_]*)\s*\{")
METHOD_PATTERN = re.compile(r"(?m)^\s*void\s+(test_[a-z0-9_]+)\s*\(\)\s*\{")


def is_official_feature_dir(path: Path) -> bool:
    return path.is_dir() and not path.name.startswith("_") and not path.name.startswith(".")


def official_feature_names() -> set[str]:
    names: set[str] = set()
    for feature_dir in iter_feature_dirs():
        feature_brief = feature_dir / "feature-brief.md"
        if not feature_brief.exists():
            continue
        text = feature_brief.read_text(encoding="utf-8")
        match = re.search(r"(?m)^\s*feature_name\s*:\s*(.+?)\s*$", text)
        if match:
            names.add(match.group(1).strip().strip('"').strip("'"))
    return names


def upgrade_java_test(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    updated = text

    class_match = CLASS_DECL_PATTERN.search(updated)
    if not class_match:
        return False
    class_name = class_match.group(1)

    if not re.search(rf"(?m)^public\s+class\s+{re.escape(class_name)}\s*\{{", updated):
        updated = re.sub(
            rf"(?m)^class\s+{re.escape(class_name)}\s*\{{",
            f"public class {class_name} {{",
            updated,
            count=1,
        )

    updated = re.sub(r"(?m)^(\s*)void\s+(test_[a-z0-9_]+)\s*\(\)\s*\{", r"\1public void \2() {", updated)

    method_names = METHOD_PATTERN.findall(updated)
    if method_names and "public static void main(String[] args)" not in updated:
        main_lines = [
            "",
            "    public static void main(String[] args) {",
            f"        {class_name} test = new {class_name}();",
        ]
        for method_name in method_names:
            main_lines.append(f"        test.{method_name}();")
        main_lines.extend(
            [
                "    }",
                "",
            ]
        )
        updated = updated.rstrip()
        if updated.endswith("}"):
            updated = updated[:-1] + "\n" + "\n".join(main_lines) + "}\n"

    if updated != text:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--feature",
        default=None,
        help="仅升级指定 feature_name 对应的 generated/design 目录",
    )
    args = parser.parse_args()

    feature_names = official_feature_names()
    if args.feature:
        feature_names = {name for name in feature_names if name == args.feature}

    changed = 0
    scanned = 0
    for feature_name in sorted(feature_names):
        feature_dir = DESIGN_TEST_ROOT / feature_name
        if not feature_dir.exists():
            continue
        for path in sorted(feature_dir.glob("*.java")):
            scanned += 1
            if upgrade_java_test(path):
                changed += 1
                print(f"[UPDATED] {path}")

    print("[OK] 设计验证测试升级完成")
    print(f"  - scanned: {scanned}")
    print(f"  - changed: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
