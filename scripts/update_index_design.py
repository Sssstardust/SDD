#!/usr/bin/env python3
"""
update_index_design.py

Design index maintenance:
- supersede older ACTIVE entries for the same feature
- append the latest ACTIVE design intent
- require approval for high-risk designs
- block conflicts against other ACTIVE design placeholders in the same baseline
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from baseline_extractors import (
    build_design_resource_claims,
    build_exact_schema_table_claims,
    extract_events_from_async_contract,
    extract_operations_from_openapi,
    extract_paths_from_openapi,
    extract_tables_from_data_model,
)
from baseline_paths import get_active_baseline_dir
from concurrency import atomic_write_text, path_lock
from design_evidence import resolve_design_pack_dir
from feature_brief import extract_affected_components
from versioning import detect_latest_design_path, reports_dir_for_design, resolve_feature_dir


ROOT = Path(__file__).resolve().parent.parent
DESIGN_INDEX_DIR_NAME = "sdd-index-design"


def claim_matches(new_claim: dict[str, str], existing_claim: dict[str, str]) -> bool:
    if new_claim.get("resource_key") == existing_claim.get("resource_key"):
        return True
    new_kind = str(new_claim.get("kind") or "")
    existing_kind = str(existing_claim.get("kind") or "")
    new_name = str(new_claim.get("name") or "")
    existing_name = str(existing_claim.get("name") or "")
    new_table_name = str(new_claim.get("table_name") or new_name).strip().lower()
    existing_table_name = str(existing_claim.get("table_name") or existing_name).strip().lower()
    if new_kind == "operation" and existing_kind == "path" and " " in new_name:
        return new_name.split(" ", 1)[1] == existing_name
    if new_kind == "path" and existing_kind == "operation" and " " in existing_name:
        return existing_name.split(" ", 1)[1] == new_name
    if new_kind == "schema-table" and existing_kind == "table":
        return bool(new_table_name) and new_table_name == existing_table_name
    if new_kind == "table" and existing_kind == "schema-table":
        return bool(new_table_name) and new_table_name == existing_table_name
    return False


def ensure_baseline(baseline_dir: Path | None = None) -> tuple[Path, Path]:
    effective_baseline_dir = baseline_dir or get_active_baseline_dir(create=True, migrate_legacy=True)
    effective_baseline_dir.mkdir(parents=True, exist_ok=True)
    design_index = effective_baseline_dir / "sdd-index-design.json"
    design_index_dir = effective_baseline_dir / DESIGN_INDEX_DIR_NAME
    real_index = effective_baseline_dir / "sdd-index-real.json"
    if not design_index.exists():
        atomic_write_text(design_index, "[]", encoding="utf-8")
    design_index_dir.mkdir(parents=True, exist_ok=True)
    if not real_index.exists():
        atomic_write_text(real_index, "[]", encoding="utf-8")
    return design_index, real_index


def write_design_index_feature_sidecars(index_data: list[dict[str, object]], baseline_dir: Path) -> None:
    design_index_dir = baseline_dir / DESIGN_INDEX_DIR_NAME
    design_index_dir.mkdir(parents=True, exist_ok=True)

    grouped: dict[str, list[dict[str, object]]] = {}
    for item in index_data:
        if not isinstance(item, dict):
            continue
        feature_name = str(item.get("feature") or "").strip()
        if not feature_name:
            continue
        grouped.setdefault(feature_name, []).append(item)

    existing_files = {path for path in design_index_dir.glob("*.json") if path.is_file()}
    desired_files: set[Path] = set()
    for feature_name, items in grouped.items():
        target = design_index_dir / f"{feature_name}.json"
        desired_files.add(target)
        atomic_write_text(target, json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    for stale_file in sorted(existing_files - desired_files):
        stale_file.unlink(missing_ok=True)


def extract_yaml_blocks(text: str) -> list[str]:
    matches = re.findall(r"```yaml\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return matches if matches else [text]


def extract_scalar(yaml_text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", yaml_text)
    if not match:
        return None
    return match.group(1).strip().strip('"').strip("'")


def find_active_conflicts(
    index_data: list[dict[str, object]],
    *,
    intent_id: str,
    feature_name: str,
    resource_claims: list[dict[str, str]],
) -> list[dict[str, object]]:
    conflicts: list[dict[str, object]] = []
    new_claims = [item for item in resource_claims if item.get("resource_key")]

    def claims_for_item(item: dict[str, object]) -> dict[str, dict[str, str]]:
        existing_claims: dict[str, dict[str, str]] = {}
        raw_claims = item.get("resource_claims")
        if isinstance(raw_claims, list):
            for claim in raw_claims:
                if not isinstance(claim, dict):
                    continue
                resource_key = str(claim.get("resource_key") or "")
                if not resource_key:
                    continue
                existing_claims[resource_key] = {
                    "kind": str(claim.get("kind") or resource_key.split("::", 1)[0] or "unknown"),
                    "name": str(claim.get("name") or resource_key.split("::", 1)[-1]),
                    "resource_key": resource_key,
                    "component_id": str(claim.get("component_id") or ""),
                }
        if existing_claims:
            return existing_claims
        legacy_claims = build_design_resource_claims(
            paths=[str(value) for value in item.get("paths", []) if isinstance(value, str)],
            tables=[str(value) for value in item.get("tables", []) if isinstance(value, str)],
            events=[str(value) for value in item.get("events", []) if isinstance(value, str)],
            operations=[candidate for candidate in item.get("operations", []) if isinstance(candidate, dict)],
        )
        return {claim["resource_key"]: claim for claim in legacy_claims}

    for item in index_data:
        if item.get("status") != "ACTIVE":
            continue
        if item.get("intent_id") == intent_id:
            continue
        if item.get("feature") == feature_name:
            continue

        resource_conflicts: dict[str, list[str]] = {}
        existing_claims = claims_for_item(item)
        matched_resource_keys: set[str] = set()
        matched_components: set[str] = set()
        for new_claim in new_claims:
            for existing_claim in existing_claims.values():
                if not claim_matches(new_claim, existing_claim):
                    continue
                kind = str(new_claim.get("kind") or "resource")
                name = str(new_claim.get("name") or new_claim.get("resource_key") or "")
                resource_conflicts.setdefault(kind, []).append(name)
                matched_resource_keys.add(str(new_claim.get("resource_key") or ""))
                component_id = str(new_claim.get("component_id") or existing_claim.get("component_id") or "")
                if component_id:
                    matched_components.add(component_id)
                break

        if resource_conflicts:
            conflicts.append(
                {
                    "feature": item.get("feature"),
                    "intent_id": item.get("intent_id"),
                    "design_version": item.get("design_version"),
                    "resources": {key: sorted(set(values)) for key, values in resource_conflicts.items()},
                    "resource_keys": sorted(key for key in matched_resource_keys if key),
                    "components": sorted(component for component in matched_components if component),
                }
            )

    return conflicts


def update_design_index(feature_dir: Path, baseline_dir: Path | None = None) -> dict[str, object]:
    feature_brief = feature_dir / "feature-brief.md"
    if not feature_brief.exists():
        return {"result": "FAIL", "errors": [f"missing feature-brief.md: {feature_brief}"]}

    yaml_text = "\n".join(extract_yaml_blocks(feature_brief.read_text(encoding="utf-8")))
    feature_name = extract_scalar(yaml_text, "feature_name") or feature_dir.name
    risk_tier = extract_scalar(yaml_text, "risk_tier") or "low"
    affected_components = extract_affected_components(feature_brief.read_text(encoding="utf-8"))

    design_path = detect_latest_design_path(feature_dir)
    if not design_path.exists():
        return {"result": "FAIL", "errors": [f"missing design document: {design_path}"]}

    approval_path = reports_dir_for_design(feature_dir, design_path) / "approval.json"
    if risk_tier == "high":
        if not approval_path.exists():
            return {"result": "FAIL", "errors": [f"risk_tier=high but approval file is missing: {approval_path}"]}
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
        if approval.get("status") != "APPROVED":
            return {"result": "FAIL", "errors": [f"approval status is not APPROVED: {approval_path}"]}

    effective_baseline_dir = baseline_dir or get_active_baseline_dir(create=True, migrate_legacy=True)
    with path_lock(effective_baseline_dir, phase="update-design-index"):
        design_index_path, _ = ensure_baseline(effective_baseline_dir)
        raw_index_data = json.loads(design_index_path.read_text(encoding="utf-8"))
        index_data = [item for item in raw_index_data if isinstance(item, dict)]

        new_intent_id = f"{feature_name}-{design_path.stem}"
        for item in index_data:
            if item.get("feature") != feature_name:
                continue
            if item.get("intent_id") != new_intent_id:
                continue
            if item.get("status") in {"ACTIVE", "IMPLEMENTED"}:
                return {
                    "result": "SKIPPED",
                    "reason": "design index already contains a valid record for the same version",
                    "feature": feature_name,
                    "design_version": design_path.name,
                    "status": item.get("status"),
                    "index": str(design_index_path),
                }

        reports_dir = reports_dir_for_design(feature_dir, design_path)
        design_pack_dir = resolve_design_pack_dir(feature_dir, reports_dir)
        openapi_path = design_pack_dir / "接口契约.openapi.yaml"
        data_model_path = design_pack_dir / "数据模型.md"
        async_contract_path = design_pack_dir / "异步事件契约.yaml"
        paths = extract_paths_from_openapi(openapi_path)
        operations = extract_operations_from_openapi(openapi_path)
        tables = extract_tables_from_data_model(data_model_path)
        events = extract_events_from_async_contract(async_contract_path)
        schema_context = json.loads((effective_baseline_dir / "schema-context.json").read_text(encoding="utf-8")) if (effective_baseline_dir / "schema-context.json").exists() else {}
        exact_schema_table_claims = build_exact_schema_table_claims(
            schema_context,
            tables,
            affected_components=affected_components,
        )
        resource_claims = build_design_resource_claims(
            paths=paths,
            tables=tables,
            events=events,
            operations=operations,
            schema_table_claims=exact_schema_table_claims,
            omit_generic_tables_for_exact=True,
        )

        conflicts = find_active_conflicts(
            index_data,
            intent_id=new_intent_id,
            feature_name=feature_name,
            resource_claims=resource_claims,
        )
        if conflicts:
            return {
                "result": "FAIL",
                "errors": ["ACTIVE design resource conflicts detected"],
                "conflicts": conflicts,
                "index": str(design_index_path),
            }

        for item in index_data:
            if item.get("feature") == feature_name and item.get("status") == "ACTIVE":
                item["status"] = "SUPERSEDED"
                item["superseded_by"] = new_intent_id

        index_data.append(
            {
                "intent_id": new_intent_id,
                "feature": feature_name,
                "design_version": design_path.name,
                "status": "ACTIVE",
                "approved_at": datetime.now(timezone.utc).isoformat(),
                "paths": paths,
                "operations": operations,
                "tables": tables,
                "events": events,
                "resource_claims": resource_claims,
                "superseded_by": None,
                "design_pack_source": str(design_pack_dir),
            }
        )
        atomic_write_text(design_index_path, json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8")
        write_design_index_feature_sidecars(index_data, effective_baseline_dir)

    return {
        "result": "OK",
        "feature": feature_name,
        "design_version": design_path.name,
        "intent_id": new_intent_id,
        "index": str(design_index_path),
        "paths": paths,
        "operations": operations,
        "tables": tables,
        "events": events,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_dir", help="specs/<feature> directory path")
    args = parser.parse_args()

    result = update_design_index(resolve_feature_dir(args.feature_dir))
    if result.get("result") == "FAIL":
        print("[FAIL] design index update failed")
        for error in result.get("errors", []):
            print(f"  - {error}")
        for conflict in result.get("conflicts", []):
            print(
                "  - conflict: "
                f"feature={conflict.get('feature')}, "
                f"intent_id={conflict.get('intent_id')}, "
                f"resources={json.dumps(conflict.get('resources'), ensure_ascii=False)}"
            )
        return 1

    if result.get("result") == "SKIPPED":
        print("[OK] design index already contains the same effective version")
        print(f"  - feature: {result.get('feature')}")
        print(f"  - design:  {result.get('design_version')}")
        print(f"  - status:  {result.get('status')}")
        print(f"  - index:   {result.get('index')}")
        return 0

    print("[OK] design index updated")
    print(f"  - feature: {result.get('feature')}")
    print(f"  - design:  {result.get('design_version')}")
    print(f"  - index:   {result.get('index')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
