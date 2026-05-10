#!/usr/bin/env python3
"""
Domain model for gate report sections.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Violation:
    rule: str
    severity: str
    location: str | None
    detail: str

    def to_payload(self) -> dict[str, object]:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "location": self.location,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class GateSection:
    gate_name: str
    payload: dict[str, object]
    violations: tuple[Violation, ...]

    @classmethod
    def from_payload(cls, gate_name: str, payload: dict[str, object]) -> "GateSection":
        existing = payload.get("violations")
        violations: list[Violation] = []
        if isinstance(existing, list):
            for item in existing:
                if not isinstance(item, dict):
                    continue
                violations.append(
                    Violation(
                        rule=str(item.get("rule") or ""),
                        severity=str(item.get("severity") or "error"),
                        location=str(item.get("location")) if item.get("location") is not None else None,
                        detail=str(item.get("detail") or ""),
                    )
                )
        else:
            location = str(payload.get("report_file")) if payload.get("report_file") is not None else None
            for severity, key in (("error", "errors"), ("warn", "warnings")):
                items = payload.get(key)
                if not isinstance(items, list):
                    continue
                for index, detail in enumerate(items, start=1):
                    violations.append(
                        Violation(
                            rule=f"{gate_name}-{severity}-{index:03d}",
                            severity=severity,
                            location=location,
                            detail=str(detail),
                        )
                    )
        return cls(gate_name=gate_name, payload=dict(payload), violations=tuple(violations))

    def to_payload(self) -> dict[str, object]:
        payload = dict(self.payload)
        payload["violations"] = [item.to_payload() for item in self.violations]
        return payload
