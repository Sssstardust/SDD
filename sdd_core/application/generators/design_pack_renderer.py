#!/usr/bin/env python3
"""
Render minimal design-pack files for sdd-generation.
"""

from __future__ import annotations

from typing import Any

from sdd_core.application.renderers.api_doc_renderer import render_openapi_yaml, render_interface_doc
from sdd_core.application.renderers.db_doc_renderer import render_data_model, render_sql
from sdd_core.application.renderers.strategy_doc_renderer import (
    render_idempotent_strategy, render_payment_state_machine,
    render_reconcile_strategy, render_async_event_contract,
    render_external_call_strategy
)
from sdd_core.domain.design_common import unique_preserve

TAG_TO_FILES = {
    "api": ["接口契约.openapi.yaml", "接口文档.md"],
    "db-change": ["数据模型.md", "数据库变更.sql"],
    "idempotent": ["幂等策略.md"],
    "payment": ["支付状态机.md", "对账策略.md"],
    "async": ["异步事件契约.yaml"],
    "external-call": ["外部调用策略.md"],
}

def build_design_pack(context: dict[str, Any], design_version: str) -> dict[str, str]:
    tags = list(context["capability_tags"])
    pack: dict[str, str] = {}
    required_files = []
    for tag in tags:
        required_files.extend(TAG_TO_FILES.get(tag, []))

    for filename in unique_preserve(required_files):
        if filename == "接口契约.openapi.yaml":
            pack[filename] = render_openapi_yaml(context)
        elif filename == "接口文档.md":
            pack[filename] = render_interface_doc(context, design_version)
        elif filename == "数据模型.md":
            pack[filename] = render_data_model(context, design_version)
        elif filename == "数据库变更.sql":
            pack[filename] = render_sql(context)
        elif filename == "幂等策略.md":
            pack[filename] = render_idempotent_strategy(context, design_version)
        elif filename == "支付状态机.md":
            pack[filename] = render_payment_state_machine(context, design_version)
        elif filename == "对账策略.md":
            pack[filename] = render_reconcile_strategy(context, design_version)
        elif filename == "异步事件契约.yaml":
            pack[filename] = render_async_event_contract(context)
        elif filename == "外部调用策略.md":
            pack[filename] = render_external_call_strategy(context, design_version)
    return pack

