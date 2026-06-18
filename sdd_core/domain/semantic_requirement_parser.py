from __future__ import annotations
import re
import json
from pathlib import Path
from typing import Any
from sdd_core.domain.attached_project import is_fixture_attachment
from sdd_core.domain.requirement_heuristics import (
    ENTITY_TERMS, DEPENDENCY_TERMS, has_greenfield_signal,
    infer_capability_tags, infer_feature_type, infer_risk_tier,
)

HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
ENTITY_IDENTIFIER_BLACKLIST = {*HTTP_METHODS, "API", "JSON", "SQL", "PRD", "DDL", "MQ"}
API_ENTITY_TOKEN_BLACKLIST = {
    "api", "v1", "v2", "v3", "tree", "record", "records", "process", "proces",
    "definition", "definitions", "preview", "upload", "download", "push", "list",
}
BUSINESS_RULE_HINTS = (
    "必须", "不能", "严禁", "规则", "逻辑", "校验", "限制",
    "当", "如果", "否则", "流程", "步骤",
)
from sdd_core.domain.attached_project import DEFAULT_ATTACHMENT_PATH as ATTACHED_PROJECT_PATH

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


