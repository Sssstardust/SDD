#!/usr/bin/env python3
"""
Domain model for persisted feature flow state.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FlowStateSnapshot:
    feature_dir: str
    feature_name: str
    current_stage: str
    risk_tier: str
    values: dict[str, object]

    @classmethod
    def from_payload(
        cls,
        feature_dir: Path,
        payload: object,
        *,
        allowed_keys: tuple[str, ...],
    ) -> "FlowStateSnapshot":
        raw = payload if isinstance(payload, dict) else {}
        normalized: dict[str, object] = {"feature_dir": str(feature_dir)}
        for key in allowed_keys:
            if key in raw:
                normalized[key] = raw[key]

        feature_name = str(normalized.get("feature_name") or feature_dir.name)
        current_stage = str(normalized.get("current_stage") or "unknown")
        risk_tier = str(normalized.get("risk_tier") or "low")
        normalized["feature_name"] = feature_name
        normalized["current_stage"] = current_stage
        normalized["risk_tier"] = risk_tier
        return cls(
            feature_dir=str(feature_dir),
            feature_name=feature_name,
            current_stage=current_stage,
            risk_tier=risk_tier,
            values=normalized,
        )

    def to_payload(self) -> dict[str, object]:
        return dict(self.values)

