#!/usr/bin/env python3
"""
Shared heuristic rules for requirement analysis in SDD workflows.
Ensures consistency between local scripts and Agent skills.
"""

from __future__ import annotations

import re

# --- Constants ---

GREENFIELD_KEYWORDS = (
    "新建",
    "从零",
    "初始化",
    "脚手架",
    "bootstrap",
    "greenfield",
    "全新模块",
    "新项目",
    "新服务",
)

TAG_KEYWORDS: dict[str, tuple[str, ...]] = {
    "api": (
        "接口",
        "api",
        "rest",
        "http",
        "endpoint",
        "controller",
        "页面",
        "查询",
        "列表",
        "新增",
        "创建",
        "修改",
        "删除",
        "审核",
        "提交",
        "详情",
    ),
    "db-change": (
        "数据库",
        "表",
        "字段",
        "sql",
        "索引",
        "迁移",
        "schema",
        "ddl",
        "新增字段",
        "调整字段",
        "表结构",
    ),
    "payment": (
        "支付",
        "付款",
        "扣款",
        "收款",
        "退款",
        "对账",
        "账单",
        "资金",
        "分账",
        "收银",
    ),
    "idempotent": (
        "幂等",
        "重复提交",
        "重复请求",
        "token",
        "防重",
        "去重",
    ),
    "async": (
        "异步",
        "消息",
        "mq",
        "topic",
        "queue",
        "事件",
        "订阅",
        "发布",
        "回调",
        "通知",
    ),
    "external-call": (
        "外部",
        "第三方",
        "feign",
        "调用外部",
        "外部系统",
        "下游接口",
        "上游接口",
        "第三方接口",
        "合作方",
        "网关",
        "渠道",
    ),
    "security-sensitive": (
        "权限",
        "鉴权",
        "认证",
        "授权",
        "脱敏",
        "敏感",
        "审计",
        "风控",
        "隐私",
        "安全",
    ),
}

ENTITY_TERMS = (
    "订单",
    "支付",
    "支付单",
    "退款",
    "账单",
    "账户",
    "用户",
    "会员",
    "商品",
    "库存",
    "审批",
    "审核",
    "任务",
    "通知",
    "消息",
)

DEPENDENCY_TERMS = (
    "mysql",
    "postgresql",
    "oracle",
    "redis",
    "mq",
    "kafka",
    "rocketmq",
    "rabbitmq",
    "es",
    "elasticsearch",
    "支付渠道",
    "第三方",
    "外部系统",
    "短信",
    "邮件",
    "对象存储",
    "oss",
    "s3",
    "微信",
    "支付宝",
)

FEATURE_TYPE_HINTS = {
    "payment": ("支付", "付款", "退款", "扣款", "对账"),
    "review": ("审核", "审批", "复核"),
    "pricing": ("资费", "套餐", "价格", "计费"),
    "notification": ("通知", "消息", "短信", "邮件"),
    "batch": ("批量", "定时", "批处理", "任务"),
    "async": ("异步", "事件", "回调", "mq"),
    "data-change": ("字段", "表结构", "数据库", "ddl", "迁移"),
    "crud": ("新增", "创建", "修改", "删除", "列表", "详情", "查询"),
    "new-domain": ("新建", "从零", "全新模块", "新项目", "新服务"),
}

# --- Functions ---

def has_greenfield_signal(text: str) -> bool:
    lower = text.lower()
    return any(keyword.lower() in lower for keyword in GREENFIELD_KEYWORDS)

def score_tag(text: str, keywords: tuple[str, ...]) -> int:
    lower = text.lower()
    return sum(1 for keyword in keywords if keyword.lower() in lower)

def has_text_signal(text: str, signals: tuple[str, ...]) -> bool:
    return any(signal in text for signal in signals)

def infer_capability_tags(text: str, has_apis: bool = False) -> list[str]:
    scores = {tag: score_tag(text, keywords) for tag, keywords in TAG_KEYWORDS.items()}
    tags = {tag for tag, score in scores.items() if score >= 1}

    if has_apis:
        tags.add("api")
    
    # Heuristic refinements
    if scores["payment"] >= 1:
        tags.add("payment")
    if scores["async"] >= 2 or (has_text_signal(text, ("异步",)) and has_text_signal(text, ("通知", "事件", "回调"))):
        tags.add("async")
    if scores["external-call"] >= 2 or (has_text_signal(text, ("第三方",)) and has_text_signal(text, ("接口",))):
        tags.add("external-call")
    if "审核人" in text or "审核时间" in text:
        tags.add("db-change")
    if any(word in text for word in ("重复提交", "重复调用", "防重")):
        tags.add("idempotent")
    if has_text_signal(text, ("权限", "角色", "审计", "隐私")):
        tags.add("security-sensitive")

    if not tags:
        tags.add("api")

    return sorted(tags)

def infer_risk_tier(tags: set[str]) -> str:
    if "payment" in tags:
        return "high"
    if "async" in tags and "db-change" in tags:
        return "high"
    if "security-sensitive" in tags:
        return "high"
    if "external-call" in tags and "payment" in tags:
        return "high"
    return "low"

def infer_feature_type(title: str, text: str, tags: set[str]) -> str:
    lower_title = title.lower()
    lower_text = text.lower()
    
    if "payment" in tags:
        return "payment"
    
    for feature_type, hints in FEATURE_TYPE_HINTS.items():
        if any(hint.lower() in lower_title or hint.lower() in lower_text for hint in hints):
            return feature_type
            
    if "async" in tags:
        return "async"
    if "db-change" in tags:
        return "data-change"
    return "general"
