#!/usr/bin/env python3
"""
Track feature-brief ambiguity items as structured state.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from concurrency import atomic_write_text, feature_lock


AMBIGUITY_PATTERN = re.compile(r"\[AMBIGUOUS:\s*(.+?)\]")


def ambiguity_tracker_path(feature_dir: Path) -> Path:
    return feature_dir / "ambiguity-tracker.json"


def extract_ambiguities(text: str) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    in_code_block = False
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        for match in AMBIGUITY_PATTERN.finditer(raw_line):
            items.append(
                {
                    "text": match.group(1).strip(),
                    "raw_marker": match.group(0),
                    "line_number": line_number,
                }
            )
    return items


def load_tracker(feature_dir: Path) -> dict[str, object] | None:
    path = ambiguity_tracker_path(feature_dir)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def save_tracker(feature_dir: Path, payload: dict[str, object]) -> Path:
    path = ambiguity_tracker_path(feature_dir)
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def sync_ambiguity_tracker(feature_dir: Path) -> dict[str, object]:
    with feature_lock(feature_dir, phase="sync-ambiguity-tracker"):
        feature_brief = feature_dir / "feature-brief.md"
        text = feature_brief.read_text(encoding="utf-8")
        discovered = extract_ambiguities(text)
        existing = load_tracker(feature_dir) or {}
        existing_items = existing.get("items")
        reusable_by_text: dict[str, list[dict[str, object]]] = {}
        if isinstance(existing_items, list):
            for item in existing_items:
                if isinstance(item, dict):
                    reusable_by_text.setdefault(str(item.get("text") or ""), []).append(item)

        items: list[dict[str, object]] = []
        for index, discovered_item in enumerate(discovered, start=1):
            text_key = str(discovered_item["text"])
            reusable = reusable_by_text.get(text_key, [])
            previous = reusable.pop(0) if reusable else {}
            status = str(previous.get("status") or "open")
            if status not in {"open", "resolved", "waived"}:
                status = "open"
            items.append(
                {
                    "id": f"AMB-{index:03d}",
                    "text": discovered_item["text"],
                    "raw_marker": discovered_item["raw_marker"],
                    "source_file": str(feature_brief),
                    "line_number": discovered_item["line_number"],
                    "status": status,
                    "resolution": str(previous.get("resolution") or ""),
                    "updated_at": previous.get("updated_at"),
                }
            )

        tracker = {
            "feature_name": feature_dir.name,
            "source_file": str(feature_brief),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "open_count": sum(1 for item in items if item["status"] == "open"),
            "resolved_count": sum(1 for item in items if item["status"] == "resolved"),
            "waived_count": sum(1 for item in items if item["status"] == "waived"),
            "items": items,
        }
        save_tracker(feature_dir, tracker)
        return tracker


def unresolved_ambiguities(feature_dir: Path) -> list[dict[str, object]]:
    tracker = sync_ambiguity_tracker(feature_dir)
    items = tracker.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict) and item.get("status") == "open"]
