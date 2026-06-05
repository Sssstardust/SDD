#!/usr/bin/env python3
"""
Automatically generate platform-specific agent configurations from manifest.yaml.
Supported: OpenAI, Claude (Capy), Gemini.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Simple YAML parser/emitter for standard manifest fields (since PyYAML is not a dependency)
def parse_simple_yaml(text: str) -> dict:
    data = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if value.startswith("[") and value.endswith("]"):
                value = [v.strip().strip('"').strip("'") for v in value[1:-1].split(",")]
            data[key] = value
    return data

def emit_yaml(data: dict) -> str:
    lines = []
    for key, value in data.items():
        if isinstance(value, list):
            lines.append(f"{key}: [{', '.join(f'\"{v}\"' for v in value)}]")
        elif isinstance(value, dict):
            lines.append(f"{key}:")
            for k, v in value.items():
                lines.append(f"  {k}: \"{v}\"")
        else:
            # Handle multiline prompts or strings with quotes
            if "\n" in str(value) or ":" in str(value):
                lines.append(f"{key}: \"{value}\"")
            else:
                lines.append(f"{key}: {value}")
    return "\n".join(lines) + "\n"

def generate_openai(manifest: dict) -> dict:
    return {
        "name": manifest.get("name"),
        "display_name": manifest.get("display_name"),
        "description": manifest.get("description"),
        "default_prompt": manifest.get("default_prompt_template"),
        # Map parameters placeholder for now, actual implementation would parse schemas
        "parameters": {
            "p1": "placeholder",
        }
    }

def generate_claude(manifest: dict) -> dict:
    return {
        "skill": manifest.get("name"),
        "role": "expert",
        "description": manifest.get("description"),
        "prompt": manifest.get("default_prompt_template"),
    }

def generate_gemini(manifest: dict) -> dict:
    return {
        "id": manifest.get("name"),
        "label": manifest.get("display_name"),
        "summary": manifest.get("description"),
        "instruction": manifest.get("default_prompt_template"),
    }


# 每个 skill 必须满足的统一目录契约（P1-7）。
REQUIRED_SKILL_FILES = [
    "SKILL.md",
    "manifest.yaml",
    "input.schema.json",
    "output.schema.json",
]


def check_skill_contract(skill_path: Path) -> list[str]:
    """返回缺失的契约文件列表；为空表示该 skill 结构合规。"""
    return [name for name in REQUIRED_SKILL_FILES if not (skill_path / name).exists()]


def main():
    root = Path(__file__).resolve().parents[1]
    skills_dir = root / "skills"
    
    if not skills_dir.exists():
        print(f"[ERROR] Skills directory not found: {skills_dir}")
        return 1
    
    count = 0
    contract_violations = 0
    for skill_path in skills_dir.iterdir():
        if not skill_path.is_dir():
            continue
        
        manifest_file = skill_path / "manifest.yaml"
        if not manifest_file.exists():
            continue

        missing = check_skill_contract(skill_path)
        if missing:
            contract_violations += 1
            print(f"[WARN] skill '{skill_path.name}' 目录契约缺失: {', '.join(missing)}")

        print(f"[PROCESS] Generating configs for {skill_path.name}...")
        manifest = parse_simple_yaml(manifest_file.read_text(encoding="utf-8"))
        
        agents_dir = skill_path / "agents"
        agents_dir.mkdir(exist_ok=True)
        
        # OpenAI
        openai_config = generate_openai(manifest)
        (agents_dir / "openai.yaml").write_text(emit_yaml(openai_config), encoding="utf-8")
        
        # Claude
        claude_config = generate_claude(manifest)
        (agents_dir / "claude.yaml").write_text(emit_yaml(claude_config), encoding="utf-8")
        
        # Gemini
        gemini_config = generate_gemini(manifest)
        (agents_dir / "gemini.yaml").write_text(emit_yaml(gemini_config), encoding="utf-8")
        
        count += 1
    
    print(f"[OK] Generated configs for {count} skills.")
    if contract_violations:
        print(f"[WARN] {contract_violations} 个 skill 不满足统一目录契约，请补齐后重跑。")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
