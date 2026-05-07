#!/usr/bin/env python3
"""
build_workspace_hygiene.py

扫描工作区中的异常生成产物与工程卫生问题，输出：
- specs/tooling-hygiene.json
- specs/tooling-hygiene.md
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from project_artifact_paths import get_active_project_artifacts_dir
from versioning import get_primary_design_root

ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = get_active_project_artifacts_dir(create=True)
OUTPUT_BASENAME = "tooling-hygiene"
SECURITY_FILE_EXTENSIONS = {".json", ".yaml", ".yml", ".env", ".txt", ".md"}
SECURITY_RULES = (
    ("plaintext-password", re.compile(r"password\s*[:=]\s*['\"]?[^'\"\s`$][^'\"\s,}]+", re.IGNORECASE)),
    ("jdbc-connection-string", re.compile(r"jdbc:[^\r\n]+", re.IGNORECASE)),
    ("dsn-with-credentials", re.compile(r"(mysql|postgres|postgresql|oracle)://[^\r\n]+:[^\r\n@`$]+@", re.IGNORECASE)),
    ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("plaintext-secret-key", re.compile(r"secret[_-]?key\s*[:=]\s*['\"]?[^'\"\s]+", re.IGNORECASE)),
)


def iter_security_scan_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for candidate in (root / "config", root / ".spec"):
        if candidate.exists():
            files.extend(
                path
                for path in candidate.rglob("*")
                if path.is_file() and path.suffix.lower() in SECURITY_FILE_EXTENSIONS
            )

    files.extend(
        path
        for path in root.glob(".env*")
        if path.is_file() and path.name != ".env.example"
    )
    return sorted({path.resolve() for path in files})


def collect_security_issues(root: Path) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for path in iter_security_scan_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        if not text.strip():
            continue

        for rule_name, pattern in SECURITY_RULES:
            if pattern.search(text):
                issues.append(
                    {
                        "type": "security-warning",
                        "severity": "warn",
                        "path": str(path),
                        "message": f"妫€娴嬪埌鐤戜技鏄庢枃鏁忔劅淇℃伅锛屽懡涓鍒?{rule_name}",
                    }
                )
                break

    return issues


def collect_issues() -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    stray_generated = ROOT / "scripts" / "specs"
    if stray_generated.exists():
        for path in sorted(stray_generated.rglob("*")):
            if path.is_file():
                issues.append(
                    {
                        "type": "stray-generated-artifact",
                        "severity": "warn",
                        "path": str(path),
                        "message": "检测到疑似误写入 scripts/specs 下的生成产物",
                    }
                )

    for path in sorted(ROOT.glob(".tmp_*")):
        issues.append(
            {
                "type": "temp-directory",
                "severity": "info",
                "path": str(path),
                "message": "检测到临时目录，建议按需清理或归档",
            }
        )

    issues.extend(collect_security_issues(ROOT))
    return issues


def render_markdown(issues: list[dict[str, str]]) -> str:
    lines = [
        "# Tooling Hygiene",
        "",
        f"- issue 数量：`{len(issues)}`",
        "",
    ]

    if not issues:
        lines.append("- 当前未发现异常生成产物或明显工程卫生问题。")
        lines.append("")
        return "\n".join(lines)

    lines.extend(
        [
            "## 问题列表",
            "",
            "| 类型 | 严重级别 | 路径 | 说明 |",
            "| --- | --- | --- | --- |",
        ]
    )

    for issue in issues:
        lines.append(
            f"| {issue['type']} | {issue['severity']} | `{issue['path'].replace('|', '\\|')}` | {issue['message']} |"
        )

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default=str(SPECS_DIR),
        help="输出目录，默认写到当前附着项目对应的项目级产物目录",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    issues = collect_issues()
    payload = {
        "issue_count": len(issues),
        "issues": issues,
    }

    json_path = output_dir / f"{OUTPUT_BASENAME}.json"
    md_path = output_dir / f"{OUTPUT_BASENAME}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(issues), encoding="utf-8")

    print("[OK] tooling-hygiene 已生成")
    print(f"  - json: {json_path}")
    print(f"  - md:   {md_path}")
    print(f"  - issues: {len(issues)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
