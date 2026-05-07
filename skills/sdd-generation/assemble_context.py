#!/usr/bin/env python3
"""
Assemble structured context for sdd-generation.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BASELINE_DIR = ROOT / ".spec" / "baseline"
ARCH_STANDARD_SERVER = ROOT / "mcp-servers" / "arch-standard" / "dist" / "server.js"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def extract_yaml_blocks(text: str) -> list[str]:
    matches = re.findall(r"```yaml\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return matches if matches else [text]


def extract_scalar(yaml_text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", yaml_text)
    if not match:
        return None
    return match.group(1).strip().strip('"').strip("'")


def extract_list_items(yaml_text: str, key: str) -> list[str]:
    lines = yaml_text.splitlines()
    items: list[str] = []
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
            items.append(stripped[2:].strip().strip('"').strip("'"))
    return items


def extract_requirements_from_yaml(yaml_text: str) -> list[dict[str, str]]:
    requirements: list[dict[str, str]] = []
    lines = yaml_text.splitlines()
    current: dict[str, str] | None = None
    in_requirements = False
    in_description = False
    description_lines: list[str] = []

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        if not in_requirements:
            if re.match(r"^\s*requirements\s*:\s*$", line):
                in_requirements = True
            continue

        if not stripped:
            continue

        if re.match(r"^\s*-\s+req_id\s*:\s*", line):
            if current:
                if description_lines:
                    current["description"] = "\n".join(description_lines).strip()
                requirements.append(current)
            current = {"req_id": stripped.split(":", 1)[1].strip()}
            description_lines = []
            in_description = False
            continue

        if current is None:
            continue

        if re.match(r"^\s*priority\s*:\s*", line):
            current["priority"] = stripped.split(":", 1)[1].strip()
            continue
        if re.match(r"^\s*title\s*:\s*", line):
            current["title"] = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            continue
        if re.match(r"^\s*description\s*:\s*\|-\s*$", line):
            in_description = True
            description_lines = []
            continue

        if in_description:
            if re.match(r"^\s{6,}", line):
                description_lines.append(line.strip())
                continue
            in_description = False

    if current:
        if description_lines:
            current["description"] = "\n".join(description_lines).strip()
        requirements.append(current)

    return requirements


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" -•\t")


def safe_slug(value: str, fallback: str = "feature") -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug or fallback


def to_pascal(value: str, fallback: str = "Feature") -> str:
    parts = [part for part in re.split(r"[^a-zA-Z0-9]+", value) if part]
    if not parts:
        return fallback
    return "".join(part[:1].upper() + part[1:] for part in parts)


def extract_apis_from_text(text: str) -> list[dict[str, str]]:
    apis: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for match in re.finditer(r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/[A-Za-z0-9_\-./{}]+)", text):
        method = match.group(1).upper()
        path = match.group(2)
        key = (method, path)
        if key in seen:
            continue
        seen.add(key)
        apis.append(
            {
                "method": method,
                "path": path,
                "summary": f"{method} {path.rsplit('/', 1)[-1]}",
                "evidence": match.group(0),
            }
        )
    return apis


def extract_entities_from_text(text: str) -> list[dict[str, str]]:
    entities: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in re.finditer(r"\b([A-Z][A-Za-z0-9]{2,}|t_[a-z0-9_]{2,})\b", text):
        name = match.group(1)
        upper = name.upper()
        if upper in {"GET", "POST", "PUT", "PATCH", "DELETE", "API", "JSON", "SQL"}:
            continue
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        entities.append({"name": name, "kind": "domain-entity", "evidence": f"文本出现 {name}"})
    return entities[:12]


def derive_structured_prd_from_feature_brief(feature_brief: Path) -> dict[str, Any]:
    text = feature_brief.read_text(encoding="utf-8")
    yaml_blocks = extract_yaml_blocks(text)
    meta_yaml = yaml_blocks[0] if yaml_blocks else text
    req_yaml = yaml_blocks[1] if len(yaml_blocks) > 1 else text

    feature_name = extract_scalar(meta_yaml, "feature_name") or feature_brief.parent.name
    feature_type = extract_scalar(meta_yaml, "feature_type") or "general"
    one_liner = extract_scalar(meta_yaml, "one_liner") or feature_name
    project_mode = extract_scalar(meta_yaml, "project_mode") or "brownfield"
    capability_tags = extract_list_items(meta_yaml, "capability_tags")
    risk_tier = extract_scalar(meta_yaml, "risk_tier") or "low"
    requirements = extract_requirements_from_yaml(req_yaml)

    ambiguities: list[str] = []
    ambiguity_section = re.search(r"(?ms)^##\s+3\.\s*歧义与待澄清项\s*(.*?)(?=^##\s+4\.|\Z)", text)
    if ambiguity_section:
        for line in ambiguity_section.group(1).splitlines():
            stripped = line.strip()
            if stripped.startswith("- [AMBIGUOUS:"):
                ambiguities.append(stripped[13:-1].strip() if stripped.endswith("]") else stripped)

    apis = extract_apis_from_text(text)
    entities = extract_entities_from_text(text)

    return {
        "status": "ready",
        "feature_name": feature_name,
        "feature_type": feature_type,
        "one_liner": one_liner,
        "project_mode": project_mode,
        "project_mode_source": extract_scalar(meta_yaml, "project_mode_source") or "feature-brief",
        "project_mode_confidence": float(extract_scalar(meta_yaml, "project_mode_confidence") or 0.8),
        "project_mode_evidence": extract_list_items(meta_yaml, "project_mode_evidence"),
        "project_mode_confirmed_by": extract_scalar(meta_yaml, "project_mode_confirmed_by") or "zhangsan",
        "capability_tags": capability_tags,
        "risk_tier": risk_tier,
        "requirements": requirements,
        "ambiguities": ambiguities,
        "entities": entities,
        "apis": apis,
        "business_rules": [],
        "dependencies": [],
        "metadata": {
            "source_file": str(feature_brief),
            "generated_at": "",
            "generator": "feature-brief-fallback",
            "ai_used": False,
            "notes": ["由 feature-brief 回推 structured_prd"],
        },
    }


def load_structured_prd(workspace: Path) -> dict[str, Any]:
    structured_prd_path = workspace / "structured-prd.json"
    if structured_prd_path.exists():
        data = read_json(structured_prd_path)
        if isinstance(data, dict):
            return data

    feature_brief = workspace / "feature-brief.md"
    if feature_brief.exists():
        return derive_structured_prd_from_feature_brief(feature_brief)

    raise FileNotFoundError(f"缺少 structured-prd.json 和 feature-brief.md: {workspace}")


def load_module_map() -> list[dict[str, Any]]:
    path = BASELINE_DIR / "module-map.json"
    if not path.exists():
        return []
    data = read_json(path)
    if isinstance(data, dict):
        classes = data.get("classes", [])
        if isinstance(classes, list):
            return [item for item in classes if isinstance(item, dict)]
    return []


def load_schema_context() -> list[dict[str, Any]]:
    path = BASELINE_DIR / "schema-context.json"
    if not path.exists():
        return []
    data = read_json(path)
    if isinstance(data, dict):
        tables = data.get("tables", [])
        if isinstance(tables, list):
            return [item for item in tables if isinstance(item, dict)]
    return []


def load_arch_constraints(feature_type: str, tags: list[str]) -> tuple[list[str], dict[str, Any] | None, str]:
    if not ARCH_STANDARD_SERVER.exists():
        return fallback_constraints(tags, "brownfield"), None, "fallback"

    payload = {
        "feature_type": feature_type or "general",
        "capability_tags": tags,
    }
    result = subprocess.run(
        ["node", str(ARCH_STANDARD_SERVER), "--tool", "get_feature_rules", "--arguments", json.dumps(payload, ensure_ascii=False)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        return fallback_constraints(tags, "brownfield"), None, "fallback"
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return fallback_constraints(tags, "brownfield"), None, "fallback"
    if not isinstance(data, dict):
        return fallback_constraints(tags, "brownfield"), None, "fallback"

    constraints = data.get("constraints", {})
    if not isinstance(constraints, dict):
        return fallback_constraints(tags, "brownfield"), None, "fallback"

    must = [str(item) for item in constraints.get("must", []) if isinstance(item, str)]
    forbidden = [str(item) for item in constraints.get("forbidden", []) if isinstance(item, str)]
    summary = must + [f"禁止：{item}" for item in forbidden]
    return summary, data, "mcp"


def collect_match_tokens(structured_prd: dict[str, Any], workspace: Path) -> list[str]:
    tokens: set[str] = set()
    feature_name = str(structured_prd.get("feature_name") or workspace.name)
    feature_type = str(structured_prd.get("feature_type") or "")
    for raw in [feature_name, feature_type, workspace.name]:
        for part in re.split(r"[^a-zA-Z0-9]+", raw):
            if len(part) >= 3:
                tokens.add(part.lower())

    for entity in structured_prd.get("entities", []) or []:
        name = entity.get("name") if isinstance(entity, dict) else str(entity)
        for part in re.split(r"[^a-zA-Z0-9]+", str(name)):
            if len(part) >= 3:
                tokens.add(part.lower())

    for api in structured_prd.get("apis", []) or []:
        path = api.get("path") if isinstance(api, dict) else ""
        for part in re.split(r"[^a-zA-Z0-9]+", str(path)):
            if len(part) >= 3 and part.lower() not in {"api"}:
                tokens.add(part.lower())

    return sorted(tokens)


def filter_module_map(classes: list[dict[str, Any]], tokens: list[str]) -> list[dict[str, Any]]:
    if not tokens:
        return classes[:8]
    matched = []
    for item in classes:
        haystack = " ".join(
            [
                str(item.get("class_name") or ""),
                str(item.get("simple_name") or ""),
                str(item.get("source_file") or ""),
                " ".join(str(method) for method in item.get("public_methods", []) if isinstance(method, str)),
            ]
        ).lower()
        if any(token in haystack for token in tokens):
            matched.append(item)
    return matched


def filter_schema_context(tables: list[dict[str, Any]], tokens: list[str]) -> list[dict[str, Any]]:
    if not tokens:
        return tables[:6]
    matched = []
    for item in tables:
        haystack = " ".join(
            [
                str(item.get("table_name") or ""),
                " ".join(str(col) for col in item.get("columns", []) if isinstance(col, str)),
                " ".join(str(src) for src in item.get("sources", []) if isinstance(src, str)),
            ]
        ).lower()
        if any(token in haystack for token in tokens):
            matched.append(item)
    return matched


def fallback_constraints(tags: list[str], project_mode: str) -> list[str]:
    constraints = [
        "分层调用符合规范",
        "事务边界清晰",
        "异常处理符合规范",
        "接口契约已落盘",
    ]
    if "db-change" in tags:
        constraints.append("数据库变更必须包含回滚")
    if "idempotent" in tags:
        constraints.append("幂等策略必须包含幂等键、冲突处理、TTL")
    if "payment" in tags:
        constraints.append("支付设计必须包含状态机、事务边界、对账与补偿")
    if "external-call" in tags:
        constraints.append("外部调用必须说明超时、重试、熔断")
    if "async" in tags:
        constraints.append("异步链路必须说明事件契约、重试与死信")
    if project_mode == "greenfield":
        constraints.append("greenfield 场景必须标记新领域边界与脚手架约束")
    return constraints


def assemble(workspace: str | Path) -> dict[str, Any]:
    workspace_path = Path(workspace).resolve()
    structured_prd = load_structured_prd(workspace_path)
    tags = list(structured_prd.get("capability_tags") or [])
    project_mode = str(structured_prd.get("project_mode") or "brownfield")
    tokens = collect_match_tokens(structured_prd, workspace_path)
    feature_type = str(structured_prd.get("feature_type") or "general")

    all_classes = load_module_map()
    matched_classes = filter_module_map(all_classes, tokens)

    all_tables = load_schema_context()
    matched_tables = filter_schema_context(all_tables, tokens)

    scenario = project_mode
    warnings: list[str] = []
    errors: list[str] = []

    if project_mode == "greenfield":
        scenario = "greenfield"
    elif not matched_classes:
        scenario = "new-domain"
        warnings.append("未匹配到相关存量类，切换为新领域模式")
    else:
        scenario = "brownfield"

    if "db-change" in tags and not matched_tables:
        if scenario == "brownfield":
            warnings.append("未匹配到相关表结构事实，数据库设计将以保守模式输出")
        else:
            warnings.append("新领域模式下未匹配到表结构事实，将生成待确认的数据模型占位")

    feature_name = str(structured_prd.get("feature_name") or workspace_path.name)
    feature_slug = safe_slug(feature_name, safe_slug(workspace_path.name, "feature"))
    feature_pascal = to_pascal(feature_name, to_pascal(workspace_path.name, "Feature"))
    constraints, arch_standard, arch_standard_source = load_arch_constraints(feature_type, tags)
    if not constraints:
        constraints = fallback_constraints(tags, project_mode)
        arch_standard_source = "fallback"
    if arch_standard_source == "fallback":
        warning = "arch-standard MCP 不可用，已回退到 fallback_constraints"
        print(f"[WARN] {warning}", file=sys.stderr)
        warnings.append(warning)

    return {
        "workspace": str(workspace_path),
        "feature_dir_name": workspace_path.name,
        "feature_name": feature_name,
        "feature_slug": feature_slug,
        "feature_pascal": feature_pascal,
        "feature_type": str(structured_prd.get("feature_type") or "general"),
        "project_mode": project_mode,
        "scenario": scenario,
        "capability_tags": tags,
        "risk_tier": str(structured_prd.get("risk_tier") or "low"),
        "structured_prd": structured_prd,
        "module_map": {
            "matched_classes": matched_classes,
            "all_class_count": len(all_classes),
            "tokens": tokens,
        },
        "schema_context": {
            "matched_tables": matched_tables,
            "all_table_count": len(all_tables),
        },
        "constraints": constraints,
        "arch_standard": arch_standard,
        "arch_standard_source": arch_standard_source,
        "warnings": warnings,
        "errors": errors,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("workspace")
    args = parser.parse_args()
    print(json.dumps(assemble(args.workspace), ensure_ascii=False, indent=2))
