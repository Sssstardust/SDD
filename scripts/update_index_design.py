#!/usr/bin/env python3
"""
update_index_design.py

设计态索引写入：
- 如果同 feature 的旧 ACTIVE 条目存在，则标记为 SUPERSEDED
- 写入新的 ACTIVE 条目
- risk_tier=high 时必须先通过审批
- 对同一 design-vN 重跑时保持幂等
- 写入前检查同 baseline 下其他 ACTIVE 设计的 API / 表 / 事件占位冲突
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from baseline_extractors import extract_events_from_async_contract, extract_paths_from_openapi, extract_tables_from_data_model
from baseline_paths import get_active_baseline_dir
from design_evidence import resolve_design_pack_dir
from versioning import detect_latest_design_path, reports_dir_for_design, resolve_feature_dir


ROOT = Path(__file__).resolve().parent.parent
def ensure_baseline(baseline_dir: Path | None = None) -> tuple[Path, Path]:
    baseline_dir = baseline_dir or get_active_baseline_dir(create=True, migrate_legacy=True)
    baseline_dir.mkdir(parents=True, exist_ok=True)
    design_index = baseline_dir / "sdd-index-design.json"
    real_index = baseline_dir / "sdd-index-real.json"
    if not design_index.exists():
        design_index.write_text("[]", encoding="utf-8")
    if not real_index.exists():
        real_index.write_text("[]", encoding="utf-8")
    return design_index, real_index


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
    paths: list[str],
    tables: list[str],
    events: list[str],
) -> list[dict[str, object]]:
    conflicts: list[dict[str, object]] = []
    new_resources = {
        "paths": set(paths),
        "tables": set(tables),
        "events": set(events),
    }

    for item in index_data:
        if item.get("status") != "ACTIVE":
            continue
        if item.get("intent_id") == intent_id:
            continue
        if item.get("feature") == feature_name:
            continue

        resource_conflicts: dict[str, list[str]] = {}
        for resource_name, new_values in new_resources.items():
            existing_values = {
                str(value)
                for value in item.get(resource_name, [])  # type: ignore[arg-type]
                if isinstance(value, str)
            }
            overlap = sorted(new_values & existing_values)
            if overlap:
                resource_conflicts[resource_name] = overlap

        if resource_conflicts:
            conflicts.append(
                {
                    "feature": item.get("feature"),
                    "intent_id": item.get("intent_id"),
                    "design_version": item.get("design_version"),
                    "resources": resource_conflicts,
                }
            )

    return conflicts


def update_design_index(feature_dir: Path, baseline_dir: Path | None = None) -> dict[str, object]:
    feature_brief = feature_dir / "feature-brief.md"
    if not feature_brief.exists():
        return {"result": "FAIL", "errors": [f"缺少 feature-brief.md: {feature_brief}"]}

    yaml_text = "\n".join(extract_yaml_blocks(feature_brief.read_text(encoding="utf-8")))
    feature_name = extract_scalar(yaml_text, "feature_name") or feature_dir.name
    risk_tier = extract_scalar(yaml_text, "risk_tier") or "low"

    design_path = detect_latest_design_path(feature_dir)
    if not design_path.exists():
        return {"result": "FAIL", "errors": [f"缺少设计文档: {design_path}"]}

    approval_path = reports_dir_for_design(feature_dir, design_path) / "approval.json"
    if risk_tier == "high":
        if not approval_path.exists():
            return {"result": "FAIL", "errors": [f"risk_tier=high，但缺少审批文件: {approval_path}"]}
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
        if approval.get("status") != "APPROVED":
            return {"result": "FAIL", "errors": [f"审批状态不是 APPROVED: {approval_path}"]}

    design_index_path, _ = ensure_baseline(baseline_dir)
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
                "reason": "设计态索引已存在同版本有效记录，跳过重复写入",
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
    tables = extract_tables_from_data_model(data_model_path)
    events = extract_events_from_async_contract(async_contract_path)

    conflicts = find_active_conflicts(
        index_data,
        intent_id=new_intent_id,
        feature_name=feature_name,
        paths=paths,
        tables=tables,
        events=events,
    )
    if conflicts:
        return {
            "result": "FAIL",
            "errors": ["设计态索引 ACTIVE 资源占位冲突"],
            "conflicts": conflicts,
            "index": str(design_index_path),
        }

    for item in index_data:
        if item.get("feature") == feature_name and item.get("status") == "ACTIVE":
            item["status"] = "SUPERSEDED"
            item["superseded_by"] = new_intent_id

    new_item = {
        "intent_id": new_intent_id,
        "feature": feature_name,
        "design_version": design_path.name,
        "status": "ACTIVE",
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "paths": paths,
        "tables": tables,
        "events": events,
        "superseded_by": None,
        "design_pack_source": str(design_pack_dir),
    }
    index_data.append(new_item)
    design_index_path.write_text(json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "result": "OK",
        "feature": feature_name,
        "design_version": design_path.name,
        "intent_id": new_intent_id,
        "index": str(design_index_path),
        "paths": paths,
        "tables": tables,
        "events": events,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    args = parser.parse_args()

    result = update_design_index(resolve_feature_dir(args.feature_dir))
    if result.get("result") == "FAIL":
        print("[FAIL] 设计态索引写入失败")
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
        print("[OK] 设计态索引已存在同版本有效记录，跳过重复写入")
        print(f"  - feature: {result.get('feature')}")
        print(f"  - design:  {result.get('design_version')}")
        print(f"  - status:  {result.get('status')}")
        print(f"  - index:   {result.get('index')}")
        return 0

    print("[OK] 设计态索引写入完成")
    print(f"  - feature: {result.get('feature')}")
    print(f"  - design:  {result.get('design_version')}")
    print(f"  - index:   {result.get('index')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
