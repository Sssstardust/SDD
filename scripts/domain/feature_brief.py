#!/usr/bin/env python3
"""
Domain model for feature-brief metadata.
"""

from __future__ import annotations

from dataclasses import dataclass

from infrastructure.sdd_yaml import get_list, get_scalar, load_merged_yaml_mapping


from typing import Any


@dataclass(frozen=True)
class FeatureBrief:
    feature_name: str
    risk_tier: str
    project_mode: str
    affected_components: tuple[str, ...]
    logic_atoms: tuple[dict[str, Any], ...] = ()

    @classmethod
    def from_text(cls, text: str, *, feature_dir_name: str = "") -> "FeatureBrief":
        data = load_merged_yaml_mapping(text)
        feature_name = (get_scalar(data, "feature_name", feature_dir_name) or feature_dir_name).strip()
        risk_tier = (get_scalar(data, "risk_tier", "low") or "low").strip().lower()
        project_mode = (get_scalar(data, "project_mode", "brownfield") or "brownfield").strip().lower()

        seen: set[str] = set()
        affected_components: list[str] = []
        for item in get_list(data, "affected_components"):
            normalized = str(item).strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                affected_components.append(normalized)

        logic_atoms = []
        for atom in get_list(data, "logic_atoms"):
            if isinstance(atom, dict):
                logic_atoms.append(atom)

        return cls(
            feature_name=feature_name,
            risk_tier=risk_tier,
            project_mode=project_mode,
            affected_components=tuple(affected_components),
            logic_atoms=tuple(logic_atoms),
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "feature_name": self.feature_name,
            "risk_tier": self.risk_tier,
            "project_mode": self.project_mode,
            "affected_components": list(self.affected_components),
            "logic_atoms": list(self.logic_atoms),
        }

