#!/usr/bin/env python3
"""
Domain models for baseline payloads.
"""

from __future__ import annotations

from dataclasses import dataclass


def _normalize_component_ids(payload: object) -> tuple[str, ...]:
    if not isinstance(payload, list):
        return ()
    seen: set[str] = set()
    values: list[str] = []
    for item in payload:
        if not isinstance(item, str):
            continue
        normalized = item.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            values.append(normalized)
    return tuple(values)


@dataclass(frozen=True)
class ModuleMapDocument:
    scanner: str | None
    confidence: str
    evidence_level: str | None
    source_signature: str | None
    ttl: object
    component_ids: tuple[str, ...]
    class_count: int

    @classmethod
    def from_payload(cls, payload: object) -> "ModuleMapDocument":
        data = payload if isinstance(payload, dict) else {}
        classes = data.get("classes")
        class_count = len(classes) if isinstance(classes, list) else 0
        return cls(
            scanner=str(data.get("scanner")) if data.get("scanner") is not None else None,
            confidence=str(data.get("confidence") or "low"),
            evidence_level=str(data.get("evidence_level")) if data.get("evidence_level") is not None else None,
            source_signature=str(data.get("source_signature")) if data.get("source_signature") is not None else None,
            ttl=data.get("ttl"),
            component_ids=_normalize_component_ids(data.get("component_ids")),
            class_count=class_count,
        )

    @property
    def is_low_confidence(self) -> bool:
        return self.confidence.lower() == "low"


@dataclass(frozen=True)
class SchemaContextDocument:
    source: str | None
    fallback_from: str | None
    confidence: str
    evidence_level: str | None
    source_signature: str | None
    ttl: object
    component_ids: tuple[str, ...]
    table_count: int

    @classmethod
    def from_payload(cls, payload: object) -> "SchemaContextDocument":
        data = payload if isinstance(payload, dict) else {}
        tables = data.get("tables")
        table_count = len(tables) if isinstance(tables, list) else 0
        return cls(
            source=str(data.get("source")) if data.get("source") is not None else None,
            fallback_from=str(data.get("fallback_from")) if data.get("fallback_from") is not None else None,
            confidence=str(data.get("confidence") or "low"),
            evidence_level=str(data.get("evidence_level")) if data.get("evidence_level") is not None else None,
            source_signature=str(data.get("source_signature")) if data.get("source_signature") is not None else None,
            ttl=data.get("ttl"),
            component_ids=_normalize_component_ids(data.get("component_ids")),
            table_count=table_count,
        )

    @property
    def uses_local_fallback(self) -> bool:
        return self.source == "local-fallback"

