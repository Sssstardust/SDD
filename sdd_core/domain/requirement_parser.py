from __future__ import annotations

from sdd_core.domain.semantic_requirement_parser import (
    first_heading_or_line as srp_first_heading_or_line,
    extract_requirements as srp_extract_requirements,
    build_one_liner as srp_build_one_liner,
    clean_sentence as srp_clean_sentence,
    make_requirement_title as srp_make_requirement_title,
    split_candidate_items as srp_split_candidate_items
)

def first_heading_or_line(text: str) -> str:
    return srp_first_heading_or_line(text)

def split_candidate_items(text: str) -> list[str]:
    return srp_split_candidate_items(text)

def clean_requirement_text(text: str) -> str:
    return srp_clean_sentence(text)

def make_requirement_title(text: str) -> str:
    return srp_make_requirement_title(text)

def extract_requirements(text: str) -> list[dict[str, str]]:
    return srp_extract_requirements(text, max_items=5, dedupe_limit=80)

def build_one_liner(title: str, requirements: list[dict[str, str]]) -> str:
    return srp_build_one_liner(title, requirements, limit=80)
