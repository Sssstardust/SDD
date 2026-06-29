from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from sdd_core.domain.requirement_heuristics import infer_risk_tier, infer_capability_tags, infer_feature_type
from sdd_core.domain.semantic_requirement_parser import (
    clean_sentence, make_requirement_title, infer_requirement_priority,
    infer_entity_kind, build_entity, summarize_api, parse_override_api,
    extract_requirements, build_one_liner, HTTP_METHODS, first_heading_or_line,
    detect_project_mode, extract_apis, extract_entities, extract_business_rules,
    extract_dependencies, extract_ambiguities, normalize_whitespace
)
from sdd_core.domain.design_common import unique_preserve


REQUIRED_CLARIFY_FIELDS = ("feature_name", "feature_type", "entities", "business_rules")

def load_schema() -> dict[str, Any]:
    import json
    SCHEMA_PATH = Path(__file__).resolve().parents[2] / "application" / "analyzers" / "schema.json"
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

def normalize_requirement(item: Any, index: int) -> dict[str, str]:
    if isinstance(item, dict):
        description = clean_sentence(str(item.get("description") or item.get("title") or ""))
        title = clean_sentence(str(item.get("title") or description or f"需求项{index}"))
        priority = str(item.get("priority") or infer_requirement_priority(description or title, index)).upper()
        if priority not in {"P0", "P1", "P2"}:
            priority = infer_requirement_priority(description or title, index)
        req_id = str(item.get("req_id") or f"REQ-{index:03d}")
        return {
            "req_id": req_id if re.fullmatch(r"REQ-\d{3}", req_id) else f"REQ-{index:03d}",
            "priority": priority,
            "title": title or f"需求项{index}",
            "description": description or title or f"需求项{index}",
        }

    description = clean_sentence(str(item))
    return {
        "req_id": f"REQ-{index:03d}",
        "priority": infer_requirement_priority(description, index),
        "title": make_requirement_title(description),
        "description": description,
    }


def normalize_entity(item: Any) -> dict[str, str]:
    if isinstance(item, dict):
        name = clean_sentence(str(item.get("name") or ""))
        kind = clean_sentence(str(item.get("kind") or infer_entity_kind(name)))
        evidence = clean_sentence(str(item.get("evidence") or "AI/override 提供"))
        return {"name": name, "kind": kind, "evidence": evidence}

    name = clean_sentence(str(item))
    return build_entity(name, "AI/override 提供")


def normalize_api(item: Any) -> dict[str, str]:
    if isinstance(item, dict):
        method = clean_sentence(str(item.get("method") or "CALL")).upper()
        if method not in {*HTTP_METHODS, "CALL"}:
            method = "CALL"
        path = clean_sentence(str(item.get("path") or item.get("url") or ""))
        summary = clean_sentence(str(item.get("summary") or summarize_api(path, method)))
        evidence = clean_sentence(str(item.get("evidence") or "AI/override 提供"))
        return {"method": method, "path": path, "summary": summary, "evidence": evidence}

    return parse_override_api(str(item))


def unique_strings(items: list[str]) -> list[str]:
    cleaned_items = [clean_sentence(x) for x in items]
    return unique_preserve([x for x in cleaned_items if x])


def unique_dict_items(items: list[dict[str, str]], key_fields: tuple[str, ...]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str, ...]] = set()
    for item in items:
        key = tuple(str(item.get(field, "")).strip().lower() for field in key_fields)
        if not any(key):
            continue
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def build_heuristic_result(source_path: Path, text: str, confirmed_by: str) -> dict[str, Any]:
    title = first_heading_or_line(text)
    project_mode, evidence, confidence = detect_project_mode(text)
    apis = extract_apis(text)
    requirements = extract_requirements(text)
    capability_tags = infer_capability_tags(text, bool(apis))
    entities = extract_entities(text, apis)
    business_rules = extract_business_rules(text)
    dependencies = extract_dependencies(text)
    feature_type = infer_feature_type(title, text, set(capability_tags))
    ambiguities = extract_ambiguities(text, confidence, project_mode)

    return {
        "status": "ready",
        "feature_name": normalize_whitespace(title),
        "feature_type": feature_type,
        "one_liner": build_one_liner(title, requirements),
        "project_mode": project_mode,
        "project_mode_source": "heuristic",
        "project_mode_confidence": confidence,
        "project_mode_evidence": evidence,
        "project_mode_confirmed_by": confirmed_by,
        "capability_tags": capability_tags,
        "risk_tier": infer_risk_tier(set(capability_tags)),
        "requirements": requirements,
        "ambiguities": ambiguities,
        "entities": entities,
        "apis": apis,
        "business_rules": business_rules,
        "dependencies": dependencies,
        "logic_atoms": [],
        "clarify": None,
        "metadata": {
            "source_file": str(source_path),
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "generator": "requirement-analyzer.extract",
            "ai_used": False,
            "ai_model": None,
            "notes": [],
        },
    }


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def normalize_result(data: dict[str, Any], source_path: Path, confirmed_by: str, ai_used: bool, ai_model: str | None) -> dict[str, Any]:
    normalized = dict(data)
    normalized["feature_name"] = clean_sentence(str(normalized.get("feature_name") or ""))
    normalized["feature_type"] = clean_sentence(str(normalized.get("feature_type") or "general"))
    normalized["requirements"] = [
        normalize_requirement(item, index)
        for index, item in enumerate(list(normalized.get("requirements") or []), start=1)
    ]
    if not normalized["requirements"]:
        normalized["requirements"] = extract_requirements(str(normalized.get("one_liner") or normalized["feature_name"]))

    normalized["one_liner"] = clean_sentence(
        str(normalized.get("one_liner") or build_one_liner(normalized["feature_name"], normalized["requirements"]))
    )

    normalized["project_mode"] = str(normalized.get("project_mode") or "hybrid")
    if normalized["project_mode"] not in {"brownfield", "greenfield", "hybrid"}:
        normalized["project_mode"] = "hybrid"

    project_mode_source = str(normalized.get("project_mode_source") or ("ai" if ai_used else "heuristic"))
    if project_mode_source not in {"heuristic", "ai", "manual", "mixed"}:
        project_mode_source = "mixed" if ai_used else "heuristic"
    normalized["project_mode_source"] = project_mode_source

    try:
        confidence = float(normalized.get("project_mode_confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    normalized["project_mode_confidence"] = min(max(confidence, 0.0), 1.0)

    normalized["project_mode_evidence"] = unique_strings(list(normalized.get("project_mode_evidence") or []))
    if not normalized["project_mode_evidence"]:
        normalized["project_mode_evidence"] = ["未提供 project_mode 证据"]

    normalized["project_mode_confirmed_by"] = clean_sentence(
        str(normalized.get("project_mode_confirmed_by") or confirmed_by)
    )

    normalized["capability_tags"] = unique_strings(list(normalized.get("capability_tags") or []))
    if not normalized["capability_tags"]:
        normalized["capability_tags"] = ["api"]

    normalized["risk_tier"] = infer_risk_tier(set(normalized["capability_tags"]))

    normalized["ambiguities"] = unique_strings(list(normalized.get("ambiguities") or []))
    normalized["entities"] = unique_dict_items(
        [normalize_entity(item) for item in list(normalized.get("entities") or []) if item],
        ("name",),
    )
    normalized["apis"] = unique_dict_items(
        [normalize_api(item) for item in list(normalized.get("apis") or []) if item],
        ("method", "path"),
    )
    normalized["business_rules"] = unique_strings(list(normalized.get("business_rules") or []))
    normalized["dependencies"] = unique_strings(list(normalized.get("dependencies") or []))
    normalized["logic_atoms"] = list(normalized.get("logic_atoms") or [])

    normalized["metadata"] = deep_merge(
        {
            "source_file": str(source_path),
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "generator": "requirement-analyzer.run",
            "ai_used": ai_used,
            "ai_model": ai_model,
            "notes": [],
        },
        dict(normalized.get("metadata") or {}),
    )
    normalized["metadata"]["source_file"] = str(source_path)
    normalized["metadata"]["ai_used"] = ai_used
    normalized["metadata"]["ai_model"] = ai_model
    normalized["metadata"]["notes"] = unique_strings(list(normalized["metadata"].get("notes") or []))

    return normalized


def apply_overrides(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)

    for scalar_key in ("feature_name", "feature_type", "project_mode", "project_mode_confirmed_by"):
        value = overrides.get(scalar_key)
        if value:
            result[scalar_key] = value
            if scalar_key == "project_mode":
                result["project_mode_source"] = "manual"
                result["project_mode_confidence"] = 1.0
                result.setdefault("project_mode_evidence", [])
                result["project_mode_evidence"] = unique_strings(
                    list(result["project_mode_evidence"]) + ["通过 CLI 手工覆盖 project_mode"]
                )

    if overrides.get("capability_tags"):
        result["capability_tags"] = unique_strings(
            list(result.get("capability_tags") or []) + list(overrides["capability_tags"])
        )

    if overrides.get("entities"):
        result["entities"] = list(result.get("entities") or []) + [
            build_entity(item, "CLI override") if not isinstance(item, dict) else normalize_entity(item)
            for item in overrides["entities"]
        ]

    if overrides.get("apis"):
        result["apis"] = list(result.get("apis") or []) + [
            parse_override_api(item) if not isinstance(item, dict) else normalize_api(item)
            for item in overrides["apis"]
        ]

    for list_key in ("business_rules", "dependencies", "ambiguities"):
        if overrides.get(list_key):
            result[list_key] = unique_strings(list(result.get(list_key) or []) + list(overrides[list_key]))

    extra_requirements = overrides.get("requirements") or []
    if extra_requirements:
        current = list(result.get("requirements") or [])
        start_index = len(current) + 1
        current.extend(normalize_requirement(item, start_index + offset) for offset, item in enumerate(extra_requirements))
        result["requirements"] = current

    override_notes = overrides.get("metadata_notes") or []
    if override_notes:
        result.setdefault("metadata", {})
        result["metadata"]["notes"] = unique_strings(list(result["metadata"].get("notes") or []) + override_notes)

    return result


def evaluate_clarify(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    missing_fields: list[str] = []
    questions: list[str] = []
    for field in REQUIRED_CLARIFY_FIELDS:
        value = data.get(field)
        is_missing = False
        if isinstance(value, str):
            is_missing = not clean_sentence(value)
        elif isinstance(value, list):
            is_missing = len(value) == 0
        else:
            is_missing = value in (None, "")
        if not is_missing:
            continue
        missing_fields.append(field)
        if field == "feature_name":
            questions.append("请确认该需求对应的 feature 名称。")
        elif field == "feature_type":
            questions.append("请确认 feature_type，例如 payment、sync、review、batch。")
        elif field == "entities":
            questions.append("请补充涉及的核心实体、表或领域对象。")
        elif field == "apis":
            questions.append("请补充涉及的接口或调用路径，例如 POST /api/v1/orders。")
        elif field == "business_rules":
            questions.append("请补充明确的业务规则、校验条件或状态约束。")
    return missing_fields, questions


def finalize_result(data: dict[str, Any]) -> dict[str, Any]:
    missing_fields, questions = evaluate_clarify(data)
    result = dict(data)
    result["clarify"] = None
    if not result.get("apis"):
        result["ambiguities"] = unique_strings(
            list(result.get("ambiguities") or []) + ["PRD 未明确接口路径，设计阶段需补充接口契约或调用入口。"]
        )

    if missing_fields:
        result["status"] = "clarify"
        result["clarify"] = {
            "missing_fields": missing_fields,
            "questions": questions,
            "suggested_overrides": [
                "--feature-name <name>",
                "--feature-type <type>",
                "--entity <entity>",
                "--api \"POST /path\"",
                "--business-rule \"业务规则说明\"",
                "--overrides-file <json-file>",
            ],
        }
        result["ambiguities"] = unique_strings(
            list(result.get("ambiguities") or [])
            + [f"缺少关键信息字段：{', '.join(missing_fields)}。"]
        )
    else:
        result["status"] = "ready"

    if not result.get("risk_tier"):
        result["risk_tier"] = infer_risk_tier(set(result.get("capability_tags") or []))
    return result


def validate_structured_prd(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema = load_schema()
    required_fields = schema.get("required", [])

    for field in required_fields:
        if field not in data:
            errors.append(f"缺少字段: {field}")

    if data.get("status") not in {"ready", "clarify"}:
        errors.append("status 必须是 ready 或 clarify")

    if data.get("project_mode") not in {"brownfield", "greenfield", "hybrid"}:
        errors.append("project_mode 非法")

    return errors


