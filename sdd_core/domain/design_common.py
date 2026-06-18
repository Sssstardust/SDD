from __future__ import annotations
import re
from typing import Any

GENERIC_ENTITY_SLUGS = {"demo", "feature", "general", "oa", "office", "platform", "system", "tob"}

def safe_slug(value: str, fallback: str = "feature") -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug or fallback

def feature_req_ids(requirements: list[dict[str, Any]]) -> str:
    ids = [str(item.get("req_id")) for item in requirements if item.get("req_id")]
    return "、".join(ids) if ids else "REQ-001"

def unique_preserve(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result

