import re
from typing import Dict, List

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

def split_numbered_items(text: str) -> List[str]:
    items: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if re.match(r"^\d+[\.\)．、]\s+", stripped):
            items.append(re.sub(r"^\d+[\.\)．、]\s+", "", stripped))
    return items

def split_bullets(text: str) -> List[str]:
    items: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if re.match(r"^[-*]\s+", stripped):
            items.append(re.sub(r"^[-*]\s+", "", stripped))
    return items

def split_paragraph_sentences(text: str) -> List[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    sentences: List[str] = []
    for paragraph in paragraphs:
        for sentence in re.split(r"[。！？；;\n]", paragraph):
            sentence = sentence.strip()
            if len(sentence) >= 10:
                sentences.append(sentence)
    return sentences

def split_candidate_items(text: str) -> List[str]:
    numbered = split_numbered_items(text)
    if numbered:
        return numbered
    bullets = split_bullets(text)
    if bullets:
        return bullets
    return split_paragraph_sentences(text)

def clean_requirement_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" -•\t")

def make_requirement_title(text: str) -> str:
    text = clean_requirement_text(text)
    first_clause = re.split(r"[。；;，,：:]", text)[0].strip()
    if len(first_clause) > 24:
        first_clause = first_clause[:24]
    return first_clause or "需求项"

def extract_requirements(text: str) -> List[Dict[str, str]]:
    candidates = [clean_requirement_text(item) for item in split_candidate_items(text)]
    candidates = [item for item in candidates if len(item) >= 8]

    deduped: List[str] = []
    seen: set[str] = set()
    for item in candidates:
        key = re.sub(r"\s+", "", item[:80])
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    if not deduped:
        deduped = ["补充需求说明，当前源文本未能自动抽取出清晰需求项"]

    result: List[Dict[str, str]] = []
    for index, item in enumerate(deduped[:5], start=1):
        result.append(
            {
                "req_id": f"REQ-{index:03d}",
                "priority": "P0" if index <= 3 else "P1",
                "title": make_requirement_title(item),
                "description": item,
            }
        )
    return result

def build_one_liner(title: str, requirements: List[Dict[str, str]]) -> str:
    if requirements:
        return requirements[0]["description"][:80]
    return title[:80]
