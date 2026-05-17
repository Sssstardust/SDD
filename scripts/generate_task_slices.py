#!/usr/bin/env python3
"""
generate_task_slices.py

Generate Task Slice drafts from feature-brief capability_tags and the design
acceptance matrix.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from concurrency import atomic_write_text, feature_lock
from versioning import detect_latest_design_path, resolve_feature_dir, reports_dir_for_design
from design_evidence import hash_file, resolve_design_pack_dir
from domain.feature_brief import FeatureBrief


ROOT = Path(__file__).resolve().parent.parent


CROSS_CUTTING_TAGS = {
    "db-change": {
        "suffix": "db",
        "title": "数据变更切片",
        "cross_cutting_checks": ["DDL 已准备", "回滚脚本已准备", "迁移后表结构可验证"],
    },
    "async": {
        "suffix": "async",
        "title": "异步事件切片",
        "cross_cutting_checks": ["Topic 或队列配置已准备", "重试策略已定义", "死信队列已定义"],
    },
    "perf": {
        "suffix": "perf",
        "title": "性能保障切片",
        "cross_cutting_checks": ["关键指标已埋点", "缓存预热策略已准备", "压测入口已明确"],
    },
    "external-call": {
        "suffix": "external",
        "title": "外部调用治理切片",
        "cross_cutting_checks": ["超时策略已定义", "熔断策略已定义", "降级策略已定义"],
    },
}


def extract_yaml_blocks(text: str) -> list[str]:
    matches = re.findall(r"```yaml\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return matches if matches else [text]


def extract_scalar(text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", text)
    if not match:
        return None
    return match.group(1).strip().strip('"').strip("'")


def extract_list_items(text: str, key: str) -> list[str]:
    items: list[str] = []
    lines = text.splitlines()
    in_block = False
    base_indent = 0
    for line in lines:
        if not in_block:
            if re.match(rf"^\s*{re.escape(key)}\s*:\s*$", line):
                in_block = True
                base_indent = len(line) - len(line.lstrip())
            continue

        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= base_indent and not line.lstrip().startswith("- "):
            break
        stripped = line.strip()
        if stripped.startswith("- "):
            value = stripped[2:].strip()
            if ":" in value:
                value = value.split(":", 1)[1].strip()
            value = value.strip('"').strip("'")
            if value:
                items.append(value)
    return items


def extract_requirements(yaml_text: str) -> list[dict[str, str]]:
    requirements: list[dict[str, str]] = []
    lines = yaml_text.splitlines()
    current: dict[str, str] | None = None

    for line in lines:
        inline_match = re.match(r"^\s*-\s*\{(.*)\}\s*$", line)
        if inline_match:
            if current:
                requirements.append(current)
                current = None
            fields: dict[str, str] = {}
            for part in inline_match.group(1).split(","):
                if ":" not in part:
                    continue
                key, value = part.split(":", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key in {"req_id", "priority", "title", "description"} and value:
                    fields[key] = value
            if "req_id" in fields:
                requirements.append(fields)
            continue
        req_match = re.match(r"^\s*-\s*req_id\s*:\s*(REQ-\d+)\s*$", line)
        if req_match:
            if current:
                requirements.append(current)
            current = {"req_id": req_match.group(1)}
            continue
        if current is None:
            continue
        field_match = re.match(r"^\s*(priority|title|description)\s*:\s*(.+?)\s*$", line)
        if field_match:
            current[field_match.group(1)] = field_match.group(2).strip().strip('"').strip("'")

    if current:
        requirements.append(current)
    return requirements


def extract_design_acceptance_matrix(design_text: str) -> dict[str, list[str]]:
    matrix: dict[str, list[str]] = {}
    req_index = 0
    acceptance_index = 2
    header_resolved = False
    for raw_line in design_text.splitlines():
        stripped = raw_line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 3:
            continue
        if not header_resolved:
            normalized = [cell.lower().replace(" ", "") for cell in cells]
            req_candidate = next((index for index, cell in enumerate(normalized) if cell in {"req-id", "reqid"}), None)
            acceptance_candidate = next(
                (
                    index
                    for index, cell in enumerate(normalized)
                    if cell in {"验收标准", "验收", "acceptancecriteria", "acceptance"}
                ),
                None,
            )
            if req_candidate is not None:
                req_index = req_candidate
            if acceptance_candidate is not None:
                acceptance_index = acceptance_candidate
            header_resolved = True
            if req_candidate is not None or acceptance_candidate is not None:
                continue
        if req_index >= len(cells) or acceptance_index >= len(cells):
            continue
        req_id = cells[req_index]
        acceptance = cells[acceptance_index]
        if re.fullmatch(r"REQ-\d+", req_id) and acceptance:
            matrix.setdefault(req_id, []).append(acceptance)
    return matrix


def yaml_list(items: list[str], indent: str = "  ") -> str:
    if not items:
        return f"{indent}- 待补充"
    return "\n".join(f'{indent}- "{item}"' for item in items)


def load_slice_template() -> str:
    template_path = ROOT / ".spec" / "templates" / "slices" / "task-slice.template.md"
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    # Fallback to internal minimal template if file is missing
    return """# {{slice_id}} {{title}}

```yaml
slice_id: {{slice_id}}
slice_type: auto-generated
depends_on: [{{depends_on}}]

req_ids:
{{req_ids_yaml}}

acceptance_checks:
{{acceptance_checks_yaml}}

cross_cutting_checks:
{{cross_cutting_checks_yaml}}

test_spec:
  type: integration
  framework: junit5
  target_class: AutoGeneratedDesignVerificationTest
  cases:
{{test_cases_yaml}}
```
{{implementation_guide_section}}
"""


def build_slice(
    *,
    slice_id: str,
    title: str,
    req_ids: list[str],
    acceptance_checks: list[str],
    depends_on: list[str] | None = None,
    cross_cutting_checks: list[str] | None = None,
    implementation_guide: str | None = None,
) -> str:
    depends_on = depends_on or []
    cross_cutting_checks = cross_cutting_checks or []
    template = load_slice_template()
    
    test_cases = []
    for index, req_id in enumerate(req_ids, start=1):
        desc = acceptance_checks[min(index - 1, len(acceptance_checks) - 1)] if acceptance_checks else req_id
        test_cases.append(f'    - id: TC-{index:03d}\n      req_id: {req_id}\n      description: "{desc}"')

    guide_section = ""
    if implementation_guide:
        guide_section = f"## 实现指南 (Implementation Guide)\n\n{implementation_guide}\n"

    content = template.replace("{{slice_id}}", slice_id)
    content = content.replace("{{title}}", title)
    content = content.replace("{{depends_on}}", ", ".join(depends_on))
    content = content.replace("{{req_ids_yaml}}", yaml_list(req_ids))
    content = content.replace("{{acceptance_checks_yaml}}", yaml_list(acceptance_checks))
    content = content.replace("{{cross_cutting_checks_yaml}}", yaml_list(cross_cutting_checks))
    content = content.replace("{{test_cases_yaml}}", "\n".join(test_cases))
    content = content.replace("{{implementation_guide_section}}", guide_section)
    
    return content.strip() + "\n"


def extract_domain_entities(design_text: str) -> list[str]:
    """Extract entity names from '## 2. 领域模型映射' section."""
    entities: list[str] = []
    lines = design_text.splitlines()
    in_section = False
    for line in lines:
        if line.strip().startswith("## 2."):
            in_section = True
            continue
        if in_section and line.strip().startswith("## "):
            break
        if in_section:
            # Match patterns like '- **User**', '- User', or table cells '| User |'
            match = re.search(r"-\s+\*\*([a-zA-Z0-9_]+)\*\*", line)
            if not match:
                match = re.search(r"-\s+([a-zA-Z0-9_]{3,})", line)
            if match:
                entities.append(match.group(1))
    return sorted(list(set(entities)))


def extract_api_endpoints(design_text: str) -> list[str]:
    """Extract API paths or names from '## 4. 接口契约' section."""
    apis: list[str] = []
    lines = design_text.splitlines()
    in_section = False
    for line in lines:
        if line.strip().startswith("## 4."):
            in_section = True
            continue
        if in_section and line.strip().startswith("## "):
            break
        if in_section:
            # Match patterns like 'POST /api/v1/user' or '`getUser`'
            match = re.search(r"(GET|POST|PUT|DELETE|PATCH)\s+([/\w\-{}\.]+)", line)
            if match:
                apis.append(f"{match.group(1)} {match.group(2)}")
            else:
                match = re.search(r"`([a-zA-Z0-9_]{3,})`", line)
                if match:
                    apis.append(match.group(1))
    return sorted(list(set(apis)))


def generate_task_slices(feature_dir: Path, *, force: bool = False) -> dict[str, object]:
    feature_brief_path = feature_dir / "feature-brief.md"
    design_path = detect_latest_design_path(feature_dir)
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    if not feature_brief_path.exists():
        return {"result": "FAIL", "errors": [f"missing feature-brief.md: {feature_brief_path}"], "created": []}
    if not design_path.exists():
        return {"result": "FAIL", "errors": [f"missing design document: {design_path}"], "created": []}

    design_content = design_path.read_text(encoding="utf-8", errors="ignore")
    brief_content = feature_brief_path.read_text(encoding="utf-8", errors="ignore")
    brief = FeatureBrief.from_text(brief_content, feature_dir_name=feature_dir.name)
    
    yaml_text = "\n".join(extract_yaml_blocks(brief_content))
    feature_name = brief.feature_name
    tags = extract_list_items(yaml_text, "capability_tags")
    requirements = extract_requirements(yaml_text)
    acceptance_matrix = extract_design_acceptance_matrix(design_content)
    
    # Map logic atoms by req_id for quick lookup
    logic_map = {atom.get("req_id"): atom.get("logic") for atom in brief.logic_atoms}
    
    entities = extract_domain_entities(design_content)
    apis = extract_api_endpoints(design_content)

    # Detect SQL files in design-pack for artifact-driven tasks
    reports_dir = reports_dir_for_design(feature_dir, design_path)
    design_pack_dir = resolve_design_pack_dir(feature_dir, reports_dir)
    sql_files = sorted(list(design_pack_dir.glob("*.sql"))) if design_pack_dir.exists() else []

    with feature_lock(feature_dir, phase="generate-task-slices"):
        created: list[str] = []
        skipped: list[str] = []
        errors: list[str] = []
        counter = 1
        
        # 1. Entity Slices
        entity_ids = []
        for entity in entities:
            slice_id = f"SLICE-{counter:03d}-ENTITY"
            target = tasks_dir / f"slice-{counter:03d}-entity-{entity.lower()}.md"
            content = build_slice(
                slice_id=slice_id,
                title=f"领域实体实现: {entity}",
                req_ids=[r["req_id"] for r in requirements[:1]], # Default to first req as anchor
                acceptance_checks=[f"实体 {entity} 结构符合设计", f"CRUD 基础逻辑通过"],
            )
            if target.exists() and not force:
                skipped.append(str(target))
            else:
                atomic_write_text(target, content, encoding="utf-8")
                created.append(str(target))
            entity_ids.append(slice_id)
            counter += 1

        # 2. API Slices
        api_ids = []
        for api in apis:
            slice_id = f"SLICE-{counter:03d}-API"
            target = tasks_dir / f"slice-{counter:03d}-api.md"
            content = build_slice(
                slice_id=slice_id,
                title=f"接口契约实现: {api}",
                req_ids=[r["req_id"] for r in requirements[:1]],
                acceptance_checks=[f"接口 {api} 响应符合定义", f"输入校验逻辑生效"],
                depends_on=entity_ids[:1] if entity_ids else [],
            )
            if target.exists() and not force:
                skipped.append(str(target))
            else:
                atomic_write_text(target, content, encoding="utf-8")
                created.append(str(target))
            api_ids.append(slice_id)
            counter += 1

        # 3. Biz/Integration Slices
        for requirement in requirements:
            req_id = requirement["req_id"]
            acceptance_checks = acceptance_matrix.get(req_id, [])
            if not acceptance_checks:
                errors.append(f"{req_id} not found in design acceptance matrix")
                continue
            
            guide_lines = []
            if req_id in logic_map:
                for logic_step in logic_map[req_id]:
                    comp = logic_step.get("component", "Unknown")
                    meth = logic_step.get("method", "unknown")
                    steps = logic_step.get("steps", [])
                    guide_lines.append(f"### 在 `{comp}` 中实现 `{meth}`")
                    for step in steps:
                        guide_lines.append(f"- [ ] {step}")
                    guide_lines.append("")
            
            target = tasks_dir / f"slice-{counter:03d}-biz.md"
            content = build_slice(
                slice_id=f"SLICE-{counter:03d}-BIZ",
                title=requirement.get("title") or req_id,
                req_ids=[req_id],
                acceptance_checks=acceptance_checks,
                depends_on=entity_ids + api_ids,
                implementation_guide="\n".join(guide_lines) if guide_lines else None
            )
            if target.exists() and not force:
                skipped.append(str(target))
            else:
                atomic_write_text(target, content, encoding="utf-8")
                created.append(str(target))
            counter += 1

        for tag in tags:
            rule = CROSS_CUTTING_TAGS.get(tag)
            if not rule:
                continue
            
            guide = None
            if tag == "db-change" and sql_files:
                guide_lines = ["### 执行并验证以下 SQL 资产："]
                for sql in sql_files:
                    try:
                        rel_path = sql.relative_to(feature_dir)
                    except ValueError:
                        rel_path = sql.name
                    guide_lines.append(f"- [ ] `{sql.name}` (路径: `{rel_path}`)")
                guide_lines.append("")
                guide_lines.append("执行命令：`python scripts/run_pipeline.py apply-db-changes` (若项目支持)")
                guide = "\n".join(guide_lines)

            target = tasks_dir / f"slice-{counter:03d}-{rule['suffix']}.md"
            all_req_ids = [item["req_id"] for item in requirements]
            all_acceptance_checks = [check for req_id in all_req_ids for check in acceptance_matrix.get(req_id, [])]
            content = build_slice(
                slice_id=f"SLICE-{counter:03d}-{str(rule['suffix']).upper()}",
                title=str(rule["title"]),
                req_ids=all_req_ids,
                acceptance_checks=all_acceptance_checks,
                cross_cutting_checks=list(rule["cross_cutting_checks"]),
                depends_on=entity_ids + api_ids + ["SLICE-001-BIZ"] if requirements else [],
                implementation_guide=guide
            )
            if target.exists() and not force:
                skipped.append(str(target))
            else:
                atomic_write_text(target, content, encoding="utf-8")
                created.append(str(target))
            counter += 1

        manifest = {
            "feature_name": feature_name,
            "design_version": design_path.name,
            "locked_design_version": design_path.name,
            "locked_design_hash": hash_file(design_path),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "result": "FAIL" if errors else "PASS",
            "created": created,
            "skipped": skipped,
            "errors": errors,
        }
        manifest_path = tasks_dir / "task-slices.generated.json"
        manifest["manifest"] = str(manifest_path)
        atomic_write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_dir", help="specs/<feature> directory path")
    parser.add_argument("--force", action="store_true", help="overwrite existing auto-generated task slices")
    args = parser.parse_args()

    result = generate_task_slices(resolve_feature_dir(args.feature_dir), force=args.force)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
