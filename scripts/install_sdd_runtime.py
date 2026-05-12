#!/usr/bin/env python3
"""
Install a self-contained SDD runtime into a target project.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUNTIME_DIR_NAME = ".sdd-runtime"

RUNTIME_COPY_SPECS: list[tuple[str, str]] = [
    ("scripts", "scripts"),
    ("skills/requirement-analyzer", "skills/requirement-analyzer"),
    ("skills/sdd-generation", "skills/sdd-generation"),
    ("document/template", "document/template"),
    ("mcp-servers/sdd-pipeline/dist", "mcp-servers/sdd-pipeline/dist"),
    ("mcp-servers/sdd-pipeline/package.json", "mcp-servers/sdd-pipeline/package.json"),
]


def should_ignore(name: str) -> bool:
    return name in {"__pycache__", ".pytest_cache", "node_modules"} or name.endswith(".pyc")


def copy_path(source: Path, target: Path) -> None:
    if source.is_dir():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            source,
            target,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc"),
        )
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def local_server_path(runtime_root: Path) -> Path:
    return runtime_root / "mcp-servers" / "sdd-pipeline" / "dist" / "server.js"


def write_agent_config_example(runtime_root: Path) -> Path:
    server_path = local_server_path(runtime_root)
    target = runtime_root / "mcp-servers" / "sdd-pipeline" / "agent-config-example.md"
    content = f"""# sdd-pipeline MCP 配置示例

这是目标项目本地的 SDD runtime MCP 配置。

## Codex / 通用 MCP JSON

```json
{{
  "mcpServers": {{
    "sdd-pipeline": {{
      "command": "node",
      "args": [
        "{server_path}"
      ]
    }}
  }}
}}
```

## 本地入口

- run pipeline: `{runtime_root / "scripts" / "run_pipeline.py"}`
- MCP server: `{server_path}`
"""
    target.write_text(content, encoding="utf-8")
    return target


def write_runtime_readme(runtime_root: Path, source_root: Path) -> Path:
    target = runtime_root / "README.md"
    content = f"""# SDD Runtime

这个目录是从 `{source_root}` 安装得到的目标项目本地 SDD runtime。

可直接使用的入口：

- `scripts/run_pipeline.py`
- `mcp-servers/sdd-pipeline/dist/server.js`

MCP 配置示例见：

- `mcp-servers/sdd-pipeline/agent-config-example.md`
"""
    target.write_text(content, encoding="utf-8")
    return target


def install_runtime(target_root: Path, runtime_dir_name: str, force: bool) -> dict[str, object]:
    runtime_root = (target_root / runtime_dir_name).resolve()
    if runtime_root.exists() and force:
        shutil.rmtree(runtime_root)
    runtime_root.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for source_rel, target_rel in RUNTIME_COPY_SPECS:
        source = (ROOT / source_rel).resolve()
        target = (runtime_root / target_rel).resolve()
        copy_path(source, target)
        copied.append(str(target))

    agent_config_path = write_agent_config_example(runtime_root)
    readme_path = write_runtime_readme(runtime_root, ROOT)

    payload = {
        "status": "ok",
        "runtime_root": str(runtime_root),
        "run_pipeline_path": str((runtime_root / "scripts" / "run_pipeline.py").resolve()),
        "mcp_server_path": str(local_server_path(runtime_root).resolve()),
        "agent_config_path": str(agent_config_path.resolve()),
        "readme_path": str(readme_path.resolve()),
        "copied_entries": copied,
    }
    manifest_path = runtime_root / "runtime-manifest.json"
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["manifest_path"] = str(manifest_path.resolve())
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-root", required=True, help="Target project root")
    parser.add_argument("--runtime-dir", default=DEFAULT_RUNTIME_DIR_NAME, help="Runtime directory name inside target root")
    parser.add_argument("--force", action="store_true", help="Replace existing runtime directory")
    args = parser.parse_args(argv)

    payload = install_runtime(Path(args.target_root).resolve(), args.runtime_dir, args.force)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
