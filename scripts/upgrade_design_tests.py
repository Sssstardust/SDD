#!/usr/bin/env python3
"""
upgrade_design_tests.py

Upgrade generated design verification tests into directly executable Java classes:
- public class
- public test methods
- main() entrypoint

Only formal features under generated/design are handled; temporary _validation-* directories are ignored.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from attached_project import DEFAULT_ATTACHMENT_PATH
from versioning import iter_feature_dirs


ROOT = Path(__file__).resolve().parent.parent
DESIGN_TEST_ROOT = ROOT / "src" / "test" / "java" / "generated" / "design"


CLASS_DECL_PATTERN = re.compile(r"(?m)^class\s+([A-Z][A-Za-z0-9_]*)\s*\{")
METHOD_PATTERN = re.compile(r"(?m)^\s*void\s+(test_[a-z0-9_]+)\s*\(\)\s*\{")


def official_feature_names(
    *,
    attachment_path: Path = DEFAULT_ATTACHMENT_PATH,
    profile: str | None = None,
) -> set[str]:
    names: set[str] = set()
    for feature_dir in iter_feature_dirs(attachment_path=attachment_path, profile=profile):
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feature", default=None, help="Only upgrade generated/design tests for the named feature")
    parser.add_argument(
        "--attachment-file",
        default=str(DEFAULT_ATTACHMENT_PATH),
        help="Attachment config path used to enumerate formal features.",
    )
    parser.add_argument("--profile", default=None, help="Optional attachment profile name.")
    args = parser.parse_args(argv)

    feature_names = official_feature_names(
        attachment_path=Path(args.attachment_file),
        profile=args.profile,
    )
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

    print("[OK] design verification test upgrade completed")
    print(f"  - scanned: {scanned}")
    print(f"  - changed: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
