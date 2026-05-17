#!/usr/bin/env python3
"""
Deterministic extraction helpers for the requirement-analyzer skill.
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[2]
# Ensure we can import from scripts/
if str(ROOT / "scripts") not in sys.path:
    sys.path.append(str(ROOT / "scripts"))

from domain.attached_project import is_fixture_attachment, load_attached_project_root
from domain.requirement_heuristics import (
    ENTITY_TERMS,
    DEPENDENCY_TERMS,
    BUSINESS_RULE_HINTS,
    has_greenfield_signal,
    infer_capability_tags,
    infer_feature_type,
    infer_risk_tier,
)

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.json"

TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030")
HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
ENTITY_IDENTIFIER_BLACKLIST = {*HTTP_METHODS, "API", "JSON", "SQL", "PRD", "DDL", "MQ"}
API_ENTITY_TOKEN_BLACKLIST = {
    "api",
    "v1",
    "v2",
    "v3",
    "tree",
    "record",
    "records",
    "process",
    "proces",
    "definition",
    "definitions",
    "preview",
    "upload",
    "download",
    "push",
    "list",
}

REQUIRED_CLARIFY_FIELDS = ("feature_name", "feature_type", "entities", "business_rules")
ATTACHED_PROJECT_PATH = ROOT / ".spec" / "attached-project.json"


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def read_text_with_fallback(path: Path) -> str:
    for encoding in TEXT_ENCODINGS:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def read_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml_bytes = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml_bytes)
    texts: list[str] = []
    for node in root.iter():
        if node.tag.endswith("}t") and node.text:
            texts.append(node.text)
        elif node.tag.endswith("}p"):
            texts.append("\n")
    normalized = "".join(texts)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def read_source(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return read_docx(path)
    if suffix in {".md", ".markdown", ".txt", ".json", ".yaml", ".yml"}:
        return read_text_with_fallback(path)
    raise ValueError(f"暂不支持的源文件类型: {path.suffix or '<none>'}")


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def clean_sentence(text: str) -> str:
    cleaned = normalize_whitespace(text).strip(" -•\t")
    cleaned = re.sub(r"^\d+[\.\)．、]\s*", "", cleaned)
    cleaned = re.sub(r"^[-*]\s*", "", cleaned)
    return cleaned


def first_heading_or_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
        if not stripped.startswith(("```", "|")):
            return re.sub(r"^[-*\d\.\)．、\s]+", "", stripped)
    return "auto-feature"


def has_text_signal(text: str, signals: tuple[str, ...]) -> bool:
    return any(signal in text for signal in signals)


def is_multi_domain_platform_demand(text: str) -> bool:
    domain_groups = (
        ("人事", "员工", "组织架构"),
        ("审批", "请假", "加班", "报销"),
        ("公告", "通知", "消息"),
        ("日程", "考勤", "打卡"),
        ("文件", "网盘", "预览"),
    )
    matched_groups = sum(1 for group in domain_groups if has_text_signal(text, group))
    return matched_groups >= 3


def load_attached_project_root() -> Path | None:
    if not ATTACHED_PROJECT_PATH.exists():
        return None
    try:
        payload = json.loads(ATTACHED_PROJECT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    project_root = payload.get("project_root")
    if not isinstance(project_root, str) or not project_root.strip():
        return None
    return Path(project_root)


def detect_project_mode(text: str) -> tuple[str, list[str], float]:
    has_green_signal = has_greenfield_signal(text)
    attached_project_root = load_attached_project_root()
    has_real_attached_project = bool(attached_project_root and not is_fixture_attachment(attached_project_root))

    evidence: list[str] = []
    if has_real_attached_project:
        evidence.append(f"检测到附着目标项目：{attached_project_root}")
    if has_green_signal:
        evidence.append("需求文本命中 greenfield 关键词")

    if has_green_signal and not has_real_attached_project:
        return "greenfield", evidence or ["需求明显为新建工程"], 0.88
    if has_green_signal and has_real_attached_project:
        evidence.append("同时存在存量工程与新建工程信号")
        return "hybrid", evidence, 0.72
    if has_real_attached_project:
        return "brownfield", evidence, 0.86
    return "hybrid", evidence or ["当前仅有 SDD 工作区上下文，缺少真实业务工程事实"], 0.60


def split_candidate_items(text: str) -> list[str]:
    numbered = []
    bullets = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if re.match(r"^\d+[\.\)．、]\s+", stripped):
            numbered.append(re.sub(r"^\d+[\.\)．、]\s+", "", stripped))
        elif re.match(r"^[-*]\s+", stripped):
            bullets.append(re.sub(r"^[-*]\s+", "", stripped))
    if numbered:
        return numbered
    if bullets:
        return bullets

    sentences: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        for sentence in re.split(r"[。！？；;\n]", paragraph):
            sentence = sentence.strip()
            if len(sentence) >= 10:
                sentences.append(sentence)
    return sentences


def make_requirement_title(text: str) -> str:
    first_clause = re.split(r"[。；;，,：:]", clean_sentence(text))[0].strip()
    if len(first_clause) > 24:
        first_clause = first_clause[:24]
    return first_clause or "需求项"


def infer_requirement_priority(text: str, index: int) -> str:
    if any(token in text for token in ("P0", "必须", "核心", "主流程", "关键")):
        return "P0"
    if any(token in text for token in ("可选", "优化", "增强", "P2")):
        return "P2"
    return "P0" if index == 1 else "P1"


def extract_requirements(text: str) -> list[dict[str, str]]:
    candidates = [clean_sentence(item) for item in split_candidate_items(text)]
    candidates = [item for item in candidates if len(item) >= 8]
    deduped: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        key = re.sub(r"\s+", "", item[:120])
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    if not deduped:
        deduped = ["补充需求说明，当前源文本未能自动抽取出清晰需求项"]

    requirements: list[dict[str, str]] = []
    for index, item in enumerate(deduped[:8], start=1):
        requirements.append(
            {
                "req_id": f"REQ-{index:03d}",
                "priority": infer_requirement_priority(item, index),
                "title": make_requirement_title(item),
                "description": item,
            }
        )
    if all(item["priority"] != "P0" for item in requirements):
        requirements[0]["priority"] = "P0"
    return requirements


def build_one_liner(title: str, requirements: list[dict[str, str]]) -> str:
    if requirements:
        return requirements[0]["description"][:120]
    return title[:120]


def infer_entity_kind(name: str) -> str:
    if name.startswith("t_"):
        return "database-table"
    if re.search(r"(system|service|client|gateway)$", name, re.IGNORECASE):
        return "external-system"
    return "domain-entity"


def build_entity(name: str, evidence: str) -> dict[str, str]:
    return {"name": name, "kind": infer_entity_kind(name), "evidence": evidence}


def extract_entities(text: str, apis: list[dict[str, str]]) -> list[dict[str, str]]:
    entities: list[dict[str, str]] = []
    seen: set[str] = set()

    for match in re.finditer(r"\b([A-Z][A-Za-z0-9]{2,}|t_[a-z0-9_]{2,})\b", text):
        name = match.group(1)
        key = name.lower()
        if name.upper() in ENTITY_IDENTIFIER_BLACKLIST:
            continue
        if key in seen:
            continue
        seen.add(key)
        entities.append(build_entity(name, f"PRD 出现标识符 {name}"))

    for term in ENTITY_TERMS:
        if term in text and term not in seen:
            seen.add(term)
            entities.append(build_entity(term, f"PRD 中出现业务对象 {term}"))

    for api in apis:
        path = api.get("path", "")
        for token in re.split(r"[/{}/_-]+", path):
            token = token.strip()
            if len(token) < 3 or token.lower() in API_ENTITY_TOKEN_BLACKLIST:
                continue
            singular = token[:-1] if token.endswith("s") and len(token) > 3 else token
            if singular.lower() in API_ENTITY_TOKEN_BLACKLIST:
                continue
            normalized = singular.capitalize()
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            entities.append(build_entity(normalized, f"由接口路径 {path} 推导"))

    return entities[:12]


def summarize_api(path: str, method: str) -> str:
    token = next((part for part in reversed(path.split("/")) if part and not part.startswith("{")), path)
    token = token.replace("-", " ").replace("_", " ").strip()
    if not token:
        token = "接口"
    return f"{method} {token}".strip()


def extract_apis(text: str) -> list[dict[str, str]]:
    apis: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for match in re.finditer(
        r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/[A-Za-z0-9_\-./{}]+)",
        text,
        re.IGNORECASE,
    ):
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
                "summary": summarize_api(path, method),
                "evidence": clean_sentence(match.group(0)),
            }
        )

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if "接口" not in stripped and "API" not in stripped.upper():
            continue
        path_match = re.search(r"(/[A-Za-z0-9_\-./{}]+)", stripped)
        if not path_match:
            continue
        method_match = re.search(r"\b(GET|POST|PUT|PATCH|DELETE)\b", stripped, re.IGNORECASE)
        method = method_match.group(1).upper() if method_match else "CALL"
        path = path_match.group(1)
        key = (method, path)
        if key in seen:
            continue
        seen.add(key)
        apis.append(
            {
                "method": method,
                "path": path,
                "summary": summarize_api(path, method),
                "evidence": stripped,
            }
        )

    return apis[:12]


def extract_business_rules(text: str) -> list[str]:
    rules: list[str] = []
    seen: set[str] = set()
    for sentence in re.split(r"[。！？\n]", text):
        sentence = clean_sentence(sentence)
        if len(sentence) < 8:
            continue
        if not any(hint in sentence for hint in BUSINESS_RULE_HINTS):
            continue
        key = sentence[:120]
        if key in seen:
            continue
        seen.add(key)
        rules.append(sentence)
    return rules[:12]


def extract_dependencies(text: str) -> list[str]:
    dependencies: list[str] = []
    seen: set[str] = set()
    lower = text.lower()
    for term in DEPENDENCY_TERMS:
        lowered_term = term.lower()
        if re.fullmatch(r"[a-z0-9_-]+", lowered_term):
            matched = re.search(rf"(?<![a-z0-9]){re.escape(lowered_term)}(?![a-z0-9])", lower) is not None
        else:
            matched = lowered_term in lower
        if matched and term not in seen:
            seen.add(term)
            dependencies.append(term)

    for sentence in re.split(r"[。！？\n]", text):
        sentence = clean_sentence(sentence)
        if len(sentence) < 6:
            continue
        if any(keyword in sentence for keyword in ("依赖", "对接", "调用", "接入")) and sentence not in seen:
            seen.add(sentence)
            dependencies.append(sentence)

    return dependencies[:12]


def extract_ambiguities(text: str, project_mode_confidence: float, project_mode: str) -> list[str]:
    ambiguities: list[str] = []
    seen: set[str] = set()

    for pattern in (r"\bTBD\b", r"待定", r"待确认", r"待补充", r"TODO", r"\?\?"):
        if re.search(pattern, text, re.IGNORECASE):
            message = "PRD 中存在待定或待确认信息。"
            if message not in seen:
                seen.add(message)
                ambiguities.append(message)

    for sentence in re.split(r"[。！？\n]", text):
        sentence = clean_sentence(sentence)
        if not sentence:
            continue
        if sentence.endswith("?") or sentence.endswith("？"):
            if sentence not in seen:
                seen.add(sentence)
                ambiguities.append(sentence)

    if project_mode_confidence < 0.8:
        message = f"project_mode 当前为 {project_mode}，置信度不足 0.8，建议人工确认。"
        if message not in seen:
            seen.add(message)
            ambiguities.append(message)

    return ambiguities[:12]


def parse_override_api(value: str) -> dict[str, str]:
    stripped = clean_sentence(value)
    match = re.match(r"^(GET|POST|PUT|PATCH|DELETE)\s+(.+)$", stripped, re.IGNORECASE)
    if match:
        method = match.group(1).upper()
        path = match.group(2).strip()
    else:
        method = "CALL"
        path = stripped
    return {
        "method": method,
        "path": path,
        "summary": summarize_api(path, method),
        "evidence": "CLI override",
    }


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
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = clean_sentence(item)
        if not cleaned:
            continue
        if cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


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


def infer_modules(tags: list[str]) -> str:
    modules = []
    if "api" in tags:
        modules.append("接口层")
    if "db-change" in tags:
        modules.append("数据库层")
    if "payment" in tags:
        modules.append("支付域")
    if "external-call" in tags:
        modules.append("外部系统集成")
    if "async" in tags:
        modules.append("异步事件链路")
    if "security-sensitive" in tags:
        modules.append("安全与审计")
    return "、".join(modules) if modules else "待补充"


def yaml_quote(text: str) -> str:
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_bullets(items: list[str], empty_text: str = "无") -> str:
    if not items:
        return f"- {empty_text}"
    return "\n".join(f"- {item}" for item in items)


def render_named_bullets(title_to_items: dict[str, list[str]]) -> str:
    lines: list[str] = []
    for title, items in title_to_items.items():
        content = "；".join(items) if items else "无"
        lines.append(f"- {title}：{content}")
    return "\n".join(lines)


def render_entity_bullets(entities: list[dict[str, str]]) -> str:
    if not entities:
        return "- 无明确实体映射"
    lines = []
    for entity in entities:
        name = entity.get("name") or "UNKNOWN"
        kind = entity.get("kind") or "unknown"
        evidence = entity.get("evidence") or "无证据说明"
        lines.append(f"- `{name}`（{kind}）：{evidence}")
    return "\n".join(lines)


def render_api_bullets(apis: list[dict[str, str]]) -> str:
    if not apis:
        return "- 无明确接口映射"
    lines = []
    for api in apis:
        method = api.get("method") or "CALL"
        path = api.get("path") or "UNKNOWN"
        summary = api.get("summary") or "无摘要"
        evidence = api.get("evidence") or "无证据说明"
        lines.append(f"- `{method} {path}`：{summary}；证据：{evidence}")
    return "\n".join(lines)


def render_structured_context_block(
    *,
    entities: list[dict[str, str]],
    apis: list[dict[str, str]],
    business_rules: list[str],
    dependencies: list[str],
) -> str:
    lines = ["entities:"]
    if entities:
        for entity in entities:
            lines.extend(
                [
                    f"  - name: {yaml_quote(entity.get('name') or '')}",
                    f"    kind: {yaml_quote(entity.get('kind') or '')}",
                    f"    evidence: {yaml_quote(entity.get('evidence') or '')}",
                ]
            )
    else:
        lines.append("  - {}")

    lines.append("apis:")
    if apis:
        for api in apis:
            lines.extend(
                [
                    f"  - method: {api.get('method') or 'CALL'}",
                    f"    path: {yaml_quote(api.get('path') or '')}",
                    f"    summary: {yaml_quote(api.get('summary') or '')}",
                    f"    evidence: {yaml_quote(api.get('evidence') or '')}",
                ]
            )
    else:
        lines.append("  - {}")

    lines.append("business_rules:")
    if business_rules:
        for rule in business_rules:
            lines.append(f"  - {yaml_quote(rule)}")
    else:
        lines.append('  - "无"')

    lines.append("dependencies:")
    if dependencies:
        for dependency in dependencies:
            lines.append(f"  - {yaml_quote(dependency)}")
    else:
        lines.append('  - "无"')

    return "\n".join(lines)


def summarize_requirements_by_priority(requirements: list[dict[str, str]]) -> dict[str, list[str]]:
    result = {"P0": [], "P1": [], "P2": []}
    for item in requirements:
        priority = str(item.get("priority") or "P1")
        title = str(item.get("title") or item.get("description") or "需求项")
        if priority not in result:
            priority = "P1"
        result[priority].append(title)
    return result


def derive_background(
    *,
    source_path: Path,
    metadata: dict[str, Any],
    feature_type: str,
    project_mode: str,
) -> str:
    generator = "AI + 规则归一化" if metadata.get("ai_used") else "规则抽取"
    source_name = Path(str(metadata.get("source_file") or source_path)).name
    if project_mode == "greenfield":
        mode_hint = "当前按 greenfield 处理，建议在设计前先补齐 Bootstrap 约束。"
    elif project_mode == "hybrid":
        mode_hint = "当前同时存在新建与存量改造信号，建议在设计前明确边界。"
    else:
        mode_hint = "当前按 brownfield 处理，默认基于现有工程事实继续设计。"
    return f"本 Feature Brief 基于 `{source_name}` 的 structured-prd 生成，需求类型为 `{feature_type}`，生成方式为 `{generator}`。{mode_hint}"


def derive_non_goal(tags: list[str], ambiguities: list[str]) -> str:
    parts = ["PRD 未明确声明的扩展流程、额外接口和新增实体不默认纳入本轮范围。"]
    if "external-call" not in tags:
        parts.append("当前范围不默认包含新增外部系统对接。")
    if "db-change" not in tags:
        parts.append("当前范围不默认包含数据库结构调整。")
    if ambiguities:
        parts.append("所有歧义项需在进入设计前清零。")
    return " ".join(parts)


def derive_success_standard(requirements: list[dict[str, str]], apis: list[dict[str, str]], entities: list[dict[str, str]]) -> str:
    p0_titles = [str(item.get("title") or "") for item in requirements if str(item.get("priority")) == "P0"]
    summary_parts = []
    if p0_titles:
        summary_parts.append("P0 需求全部可追溯并形成设计输入：" + "；".join(p0_titles[:4]))
    if apis:
        summary_parts.append(f"关键接口映射完整（{len(apis)} 项）")
    if entities:
        summary_parts.append(f"关键实体识别完整（{len(entities)} 项）")
    return "；".join(summary_parts) if summary_parts else "待补充"


def derive_risk_reason(tags: list[str]) -> str:
    tag_set = set(tags)
    reasons: list[str] = []
    if "payment" in tag_set:
        reasons.append("命中 `payment` 标签，按规范自动判定为 `high`")
    if "async" in tag_set and "db-change" in tag_set:
        reasons.append("同时命中 `async + db-change`，按规范自动判定为 `high`")
    if "security-sensitive" in tag_set:
        reasons.append("命中 `security-sensitive`，按规范自动判定为 `high`")
    if "external-call" in tag_set and "payment" in tag_set:
        reasons.append("同时命中 `external-call + payment`，按规范自动判定为 `high`")
    if not reasons:
        reasons.append("未命中高风险组合，当前维持 `low`")
    return "；".join(reasons)


def derive_risk_focus(tags: list[str], project_mode: str) -> str:
    focus: list[str] = []
    tag_set = set(tags)
    if "db-change" in tag_set:
        focus.append("数据模型、DDL 与回滚脚本")
    if "external-call" in tag_set:
        focus.append("外部调用超时、重试与熔断")
    if "async" in tag_set:
        focus.append("消息重试、死信与消费幂等")
    if "payment" in tag_set:
        focus.append("支付状态机、对账与补偿")
    if "security-sensitive" in tag_set:
        focus.append("权限控制、审计与脱敏")
    if project_mode == "greenfield":
        focus.append("Bootstrap 约束与模块边界")
    if project_mode == "hybrid":
        focus.append("存量兼容边界与新模块边界")
    if not focus:
        focus.append("P0 需求覆盖与验收矩阵")
    return "；".join(focus)


def render_logic_atoms_yaml(logic_atoms: list[dict[str, Any]]) -> str:
    if not logic_atoms:
        return "logic_atoms: []"
    lines = ["logic_atoms:"]
    for atom in logic_atoms:
        req_id = atom.get("req_id") or "REQ-???"
        lines.append(f"  - req_id: {req_id}")
        lines.append("    logic:")
        for step_group in atom.get("logic") or []:
            comp = yaml_quote(step_group.get("component") or "Unknown")
            meth = yaml_quote(step_group.get("method") or "unknown")
            lines.append(f"      - component: {comp}")
            lines.append(f"        method: {meth}")
            lines.append("        steps:")
            for step in step_group.get("steps") or []:
                lines.append(f"          - {yaml_quote(step)}")
    return "\n".join(lines)


def render_logic_atoms_bullets(logic_atoms: list[dict[str, Any]]) -> str:
    if not logic_atoms:
        return "- 无明确逻辑建模"
    lines = []
    for atom in logic_atoms:
        req_id = atom.get("req_id") or "REQ-???"
        lines.append(f"- **{req_id}** 实现路径：")
        for step_group in atom.get("logic") or []:
            comp = step_group.get("component") or "Unknown"
            meth = step_group.get("method") or "unknown"
            steps = " -> ".join(step_group.get("steps") or [])
            lines.append(f"  - `{comp}.{meth}`: {steps}")
    return "\n".join(lines)


def render_feature_brief(data: dict[str, Any], source_path: Path) -> str:
    tags = list(data.get("capability_tags") or [])
    requirements = list(data.get("requirements") or [])
    ambiguities = list(data.get("ambiguities") or [])
    entities_payload = list(data.get("entities") or [])
    apis_payload = list(data.get("apis") or [])
    business_rules = list(data.get("business_rules") or [])
    dependencies = list(data.get("dependencies") or [])
    logic_atoms = list(data.get("logic_atoms") or [])
    metadata = dict(data.get("metadata") or {})
    project_mode = str(data.get("project_mode") or "brownfield")
    project_mode_source = str(data.get("project_mode_source") or "heuristic")
    project_mode_confidence = float(data.get("project_mode_confidence") or 0.0)
    project_mode_confirmed_by = str(data.get("project_mode_confirmed_by") or "zhangsan")
    feature_name = str(data.get("feature_name") or "auto-feature")
    feature_type = str(data.get("feature_type") or "general")
    one_liner = str(data.get("one_liner") or "待补充").replace('"', "'")
    risk_tier = str(data.get("risk_tier") or "low")
    evidence_block = "\n".join(f'  - "{item}"' for item in data.get("project_mode_evidence", []))
    tags_block = "\n".join(f"  - {tag}" for tag in tags)
    requirements_block = "\n".join(
        [
            f"  - req_id: {item['req_id']}\n"
            f"    priority: {item['priority']}\n"
            f'    title: "{item["title"]}"\n'
            f"    description: |-\n"
            + "\n".join(f"      {line}" for line in str(item["description"]).splitlines())
            for item in requirements
        ]
    )
    if ambiguities:
        ambiguity_block = "\n".join(f"- [AMBIGUOUS: {item}]" for item in ambiguities)
    else:
        ambiguity_block = "- 无"

    entities = [entity["name"] for entity in entities_payload if entity.get("name")]
    apis = [f"{api['method']} {api['path']}" for api in apis_payload if api.get("path")]

    business_goal = data.get("one_liner") or "待补充"
    background = derive_background(
        source_path=source_path,
        metadata=metadata,
        feature_type=feature_type,
        project_mode=project_mode,
    )
    non_goal = derive_non_goal(tags, ambiguities)
    success_standard = derive_success_standard(requirements, apis_payload, entities_payload)
    dependency_text = "；".join(dependencies[:4]) if dependencies else "待补充"
    requirement_priority_map = summarize_requirements_by_priority(requirements)
    business_rules_block = render_bullets(business_rules, "无明确业务规则")
    entities_block = render_entity_bullets(entities_payload)
    apis_block = render_api_bullets(apis_payload)
    dependencies_block = render_bullets(dependencies, "无明确外部依赖")
    logic_atoms_block = render_logic_atoms_bullets(logic_atoms)
    structured_context_block = render_structured_context_block(
        entities=entities_payload,
        apis=apis_payload,
        business_rules=business_rules,
        dependencies=dependencies,
    )
    logic_atoms_yaml = render_logic_atoms_yaml(logic_atoms)
    risk_reason = derive_risk_reason(tags)
    risk_focus = derive_risk_focus(tags, project_mode)
    priority_summary_block = render_named_bullets(requirement_priority_map)

    return f"""# Feature Brief

**版本:** `v1.0`  
**日期:** `{datetime.now().date()}`  
**状态:** `Draft`  

---

## 1. 基本信息

```yaml
project_mode: {project_mode}
project_mode_source: {project_mode_source}
project_mode_confidence: {project_mode_confidence:.2f}
project_mode_evidence:
{evidence_block}
project_mode_confirmed_by: {project_mode_confirmed_by}

feature_name: {feature_name}
feature_type: {feature_type}
one_liner: "{one_liner}"

capability_tags:
{tags_block}

risk_tier: {risk_tier}
```

---

## 2. 需求清单
```yaml
requirements:
{requirements_block}
```

---

## 3. 逻辑原子建模 (实现预演)
```yaml
{logic_atoms_yaml}
```

{logic_atoms_block}

---

## 4. 歧义与待澄清项
{ambiguity_block}

---

## 5. 业务说明

- 背景：{background}
- 业务目标：{business_goal}
- 非 goal：{non_goal}
- 成功标准：{success_standard}

### 5.1 需求优先级映射
{priority_summary_block}

### 5.2 关键业务规则映射
{business_rules_block}

---

## 6. 依赖与影响范围
- 涉及模块：{infer_modules(tags)}
- 涉及实体：{"、".join(entities[:6]) if entities else "待补充"}
- 涉及数据库：{"是" if "db-change" in tags else "待补充"}
- 涉及外部系统：{dependency_text}
- 是否影响现有接口：{"是" if apis else "待补充"}
- 关键接口：{"；".join(apis[:4]) if apis else "待补充"}

### 6.1 实体映射
{entities_block}

### 6.2 接口映射
{apis_block}

### 6.3 依赖映射
{dependencies_block}

### 6.4 结构化补充上下文
```yaml
{structured_context_block}
```

---

## 7. 风险说明

- 风险级别：`{risk_tier}`
- 为什么当前 `risk_tier` 是这个级别：{risk_reason}
- 是否需要架构审批：{"是" if risk_tier == "high" else "否"}
- 项目模式影响：当前 `project_mode={project_mode}`，来源 `{project_mode_source}`，置信度 `{project_mode_confidence:.2f}`。
- 设计关注点：{risk_focus}
- 是否存在上线风险：需结合详细设计和实现阶段进一步确认。

---

## 8. 审阅记录

- 审阅人：
- 审阅结论：
- 审阅时间：
"""
