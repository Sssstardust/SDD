#!/usr/bin/env python3
"""
Deterministic extraction helpers for the requirement-analyzer skill.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sdd_core.infrastructure.document_readers import read_source
from sdd_core.domain.semantic_requirement_parser import (
    normalize_whitespace, clean_sentence, first_heading_or_line,
    has_text_signal, is_multi_domain_platform_demand, load_attached_project_root,
    detect_project_mode, split_candidate_items, make_requirement_title,
    infer_requirement_priority, extract_requirements, build_one_liner,
    infer_entity_kind, build_entity, extract_entities, summarize_api,
    extract_apis, extract_business_rules, extract_dependencies,
    extract_ambiguities, parse_override_api
)
from sdd_core.domain.semantic_requirement_models import (
    normalize_requirement, normalize_entity, normalize_api, unique_strings,
    unique_dict_items, build_heuristic_result, deep_merge, normalize_result,
    apply_overrides, evaluate_clarify, finalize_result, validate_structured_prd,
    load_schema
)
from sdd_core.application.renderers.semantic_brief_renderer import (
    infer_modules, yaml_quote, render_bullets, render_named_bullets,
    render_entity_bullets, render_api_bullets, render_structured_context_block,
    summarize_requirements_by_priority, derive_background, derive_non_goal,
    derive_success_standard, derive_risk_reason, derive_risk_focus,
    render_logic_atoms_yaml, render_logic_atoms_bullets, render_feature_brief
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.json"

