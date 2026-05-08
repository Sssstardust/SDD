#!/usr/bin/env python3
"""
sync_baseline.py

Minimal baseline sync:
- after Gate 5 PASS, mark matching ACTIVE design intent as IMPLEMENTED
- append the realized implementation record into the real index
- keep repeated syncs for the same design version idempotent
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
    extract_operations_from_openapi,
    extract_paths_from_openapi,
    extract_tables_from_data_model,
)
from baseline_governance import refresh_governance_baseline
from baseline_paths import get_active_baseline_dir
from concurrency import atomic_write_text, path_lock
from design_evidence import evidence_level_for_schema_context, hash_file, hash_tree, resolve_design_pack_dir
from feature_brief import extract_affected_components
from gate_report import write_gate_section
from versioning import reports_dir_for_design, resolve_design_path, resolve_feature_dir


ROOT = Path(__file__).resolve().parent.parent
BASELINE_DIR = get_active_baseline_dir(create=True, migrate_legacy=True)


def ensure_baseline(baseline_dir: Path | None = None) -> tuple[Path, Path]:
    effective_baseline_dir = baseline_dir or get_active_baseline_dir(create=True, migrate_legacy=True)
    effective_baseline_dir.mkdir(parents=True, exist_ok=True)
    design_index = effective_baseline_dir / "sdd-index-design.json"
    real_index = effective_baseline_dir / "sdd-index-real.json"
    if not design_index.exists():
        atomic_write_text(design_index, "[]", encoding="utf-8")
    if not real_index.exists():
        atomic_write_text(real_index, "[]", encoding="utf-8")
    return design_index, real_index


def extract_yaml_blocks(text: str) -> list[str]:
    matches = re.findall(r"```yaml\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return matches if matches else [text]


def extract_scalar(yaml_text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", yaml_text)
    if not match:
        return None
    return match.group(1).strip().strip('"').strip("'")


def validate_gate_report_for_sync(gate_report_path: Path, design_path: Path) -> tuple[list[str], dict[str, object]]:
    errors: list[str] = []
    if not gate_report_path.exists():
        errors.append(f"missing gate-report.json: {gate_report_path}")
        return errors, {}

    gate_report = json.loads(gate_report_path.read_text(encoding="utf-8"))
    if gate_report.get("design_version") and gate_report.get("design_version") != design_path.name:
        errors.append(
            "gate-report.json design_version does not match the target design version: "
            f"{gate_report.get('design_version')} != {design_path.name}"
        )

    for gate_name in ["gate1", "gate2", "gate3", "gate5"]:
        gate_payload = gate_report.get(gate_name)
        if not isinstance(gate_payload, dict):
            errors.append(f"gate-report.json missing {gate_name}")
            continue
        if gate_payload.get("result") != "PASS":
            errors.append(f"{gate_name} is not PASS, baseline sync is blocked: {gate_payload.get('result')}")

    gate1 = gate_report.get("gate1")
    if isinstance(gate1, dict):
        evidence = gate1.get("evidence")
        if isinstance(evidence, dict):
            expected_design_hash = evidence.get("design_hash")
            actual_design_hash = hash_file(design_path)
            if expected_design_hash and expected_design_hash != actual_design_hash:
                errors.append("design hash does not match Gate 1 evidence")

    return errors, gate_report


def sync_feature_to_baseline(
    feature_dir: Path,
    baseline_dir: Path | None = None,
    *,
    design_version: str | None = None,
) -> int:
    design_path = resolve_design_path(feature_dir, design_version)
    if not design_path.exists():
        print(f"[ERROR] missing design document: {design_path}")
        return 1

    verify_report_path = reports_dir_for_design(feature_dir, design_path) / "verify-report.json"
    feature_brief = feature_dir / "feature-brief.md"
    if not verify_report_path.exists():
        print(f"[ERROR] missing verify-report.json: {verify_report_path}")
        return 1

    verify = json.loads(verify_report_path.read_text(encoding="utf-8"))
    if verify.get("result") != "PASS":
        print(f"[FAIL] Gate 5 is not PASS, baseline sync is blocked: {verify_report_path}")
        return 1
    if verify.get("design_version") and verify.get("design_version") != design_path.name:
        print(
            "[FAIL] verify-report.json design_version does not match the target design version: "
            f"{verify.get('design_version')} != {design_path.name}"
        )
        return 1

    gate_report_path = reports_dir_for_design(feature_dir, design_path) / "gate-report.json"
    gate_errors, _ = validate_gate_report_for_sync(gate_report_path, design_path)
    if gate_errors:
        print("[FAIL] gate reports do not satisfy baseline sync conditions")
        for error in gate_errors:
            print(f"  - {error}")
        return 1

    yaml_text = "\n".join(extract_yaml_blocks(feature_brief.read_text(encoding="utf-8")))
    feature_name = extract_scalar(yaml_text, "feature_name") or feature_dir.name
    affected_components = extract_affected_components(feature_brief.read_text(encoding="utf-8"))
    intent_id = f"{feature_name}-{design_path.stem}"
    reports_dir = reports_dir_for_design(feature_dir, design_path)
    effective_baseline_dir = baseline_dir or get_active_baseline_dir(create=True, migrate_legacy=True)

    with path_lock(effective_baseline_dir, phase="sync-baseline"):
        design_index_path, real_index_path = ensure_baseline(effective_baseline_dir)
        design_index = json.loads(design_index_path.read_text(encoding="utf-8"))
        real_index = json.loads(real_index_path.read_text(encoding="utf-8"))

        existing_real = next(
            (
                item
                for item in real_index
                if item.get("feature") == feature_name
                and item.get("design_version") == design_path.name
                and item.get("source_intent_id") == intent_id
            ),
            None,
        )
        if existing_real is not None:
            refresh_governance_baseline(feature_dir.parent, effective_baseline_dir, acquire_lock=False)
            print("[OK] the same implemented baseline record already exists, skipped")
            print(f"  - feature: {feature_name}")
            print(f"  - design:  {design_path.name}")
            print(f"  - real:    {real_index_path}")
            return 0

        source_intent_id = None
        for item in design_index:
            if item.get("feature") != feature_name or item.get("intent_id") != intent_id:
                continue
            source_intent_id = item.get("intent_id")
            if item.get("status") == "ACTIVE":
                item["status"] = "IMPLEMENTED"

        design_pack_dir = resolve_design_pack_dir(feature_dir, reports_dir)
        openapi_path = design_pack_dir / "接口契约.openapi.yaml"
        data_model_path = design_pack_dir / "数据模型.md"
        module_map_path = effective_baseline_dir / "module-map.json"
        schema_context_path = effective_baseline_dir / "schema-context.json"
        verified_at = verify.get("checked_at") or datetime.now(timezone.utc).isoformat()
        evidence = {
            "design": {
                "source": str(design_path),
                "hash": hash_file(design_path),
                "evidence_level": "L3",
                "confidence": "medium",
            },
            "design_pack": {
                "source": str(design_pack_dir),
                "hash": hash_tree(design_pack_dir),
                "evidence_level": "L3",
                "confidence": "medium",
            },
            "module_map": {
                "source": str(module_map_path),
                "hash": hash_file(module_map_path),
                "evidence_level": "L2" if module_map_path.exists() else "L3",
                "confidence": "medium" if module_map_path.exists() else "low",
            },
            "schema_context": {
                "source": str(schema_context_path),
                "hash": hash_file(schema_context_path),
                "evidence_level": evidence_level_for_schema_context(schema_context_path),
                "confidence": "medium" if schema_context_path.exists() else "low",
            },
            "verify_report": {
                "source": str(verify_report_path),
                "hash": hash_file(verify_report_path),
                "evidence_level": "L1",
                "confidence": "high",
            },
        }
        real_paths = extract_paths_from_openapi(openapi_path)
        real_operations = extract_operations_from_openapi(openapi_path)
        real_tables = extract_tables_from_data_model(data_model_path)
        schema_context = json.loads(schema_context_path.read_text(encoding="utf-8")) if schema_context_path.exists() else {}
        exact_schema_table_claims = build_exact_schema_table_claims(
            schema_context,
            real_tables,
            affected_components=affected_components,
        )
        real_index.append(
            {
                "feature": feature_name,
                "design_version": design_path.name,
                "implemented_at": datetime.now(timezone.utc).isoformat(),
                "paths": real_paths,
                "operations": real_operations,
                "tables": real_tables,
                "resource_claims": build_design_resource_claims(
                    paths=real_paths,
                    tables=real_tables,
                    events=[],
                    operations=real_operations,
                    schema_table_claims=exact_schema_table_claims,
                ),
                "source_intent_id": source_intent_id,
                "design_hash": evidence["design"]["hash"],
                "design_pack_hash": evidence["design_pack"]["hash"],
                "module_map_hash": evidence["module_map"]["hash"],
                "schema_context_hash": evidence["schema_context"]["hash"],
                "verified_report": str(verify_report_path),
                "verified_at": verified_at,
                "evidence": evidence,
            }
        )

        atomic_write_text(design_index_path, json.dumps(design_index, ensure_ascii=False, indent=2), encoding="utf-8")
        atomic_write_text(real_index_path, json.dumps(real_index, ensure_ascii=False, indent=2), encoding="utf-8")
        refresh_governance_baseline(feature_dir.parent, effective_baseline_dir, acquire_lock=False)

    write_gate_section(
        reports_dir,
        gate_name="baseline_sync",
        feature_name=feature_name,
        design_version=design_path.name,
        payload={
            "result": "PASS",
            "real_index": str(real_index_path),
            "source_intent_id": source_intent_id,
            "verified_report": str(verify_report_path),
            "verified_at": verified_at,
            "evidence": evidence,
        },
    )

    print("[OK] baseline sync completed")
    print(f"  - design index: {design_index_path}")
    print(f"  - real index:   {real_index_path}")
    print(f"  - constitution: {effective_baseline_dir / 'constitution.md'}")
    print(f"  - tech debt:    {effective_baseline_dir / 'tech-debt.md'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_dir", help="specs/<feature> directory path")
    parser.add_argument("--design-version", default=None, help="explicit design-vN.md / vN / N")
    args = parser.parse_args()

    feature_dir = resolve_feature_dir(args.feature_dir)
    return sync_feature_to_baseline(feature_dir, design_version=args.design_version)


if __name__ == "__main__":
    raise SystemExit(main())
