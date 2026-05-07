#!/usr/bin/env python3
"""
design_index_lifecycle.py

设计态索引生命周期运维动作：
- cancel: 将当前设计意图标记为 CANCELLED
- archive: 将非 ACTIVE 记录迁移到独立归档文件
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from baseline_paths import get_active_baseline_dir
from versioning import detect_latest_design_path, resolve_feature_dir


ROOT = Path(__file__).resolve().parent.parent
DESIGN_INDEX_FILE = "sdd-index-design.json"
REAL_INDEX_FILE = "sdd-index-real.json"
DESIGN_ARCHIVE_FILE = "sdd-index-design.archive.json"
ARCHIVABLE_STATUSES = {"SUPERSEDED", "CANCELLED", "IMPLEMENTED"}


def ensure_design_index_files(baseline_dir: Path | None = None) -> tuple[Path, Path, Path]:
    effective_baseline_dir = baseline_dir or get_active_baseline_dir(create=True, migrate_legacy=True)
    effective_baseline_dir.mkdir(parents=True, exist_ok=True)
    design_index = effective_baseline_dir / DESIGN_INDEX_FILE
    real_index = effective_baseline_dir / REAL_INDEX_FILE
    archive_index = effective_baseline_dir / DESIGN_ARCHIVE_FILE
    if not design_index.exists():
        design_index.write_text("[]", encoding="utf-8")
    if not real_index.exists():
        real_index.write_text("[]", encoding="utf-8")
    return design_index, real_index, archive_index


def read_index(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def write_index(path: Path, payload: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_yaml_blocks(text: str) -> list[str]:
    matches = re.findall(r"```yaml\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return matches if matches else [text]


def extract_scalar(yaml_text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", yaml_text)
    if not match:
        return None
    return match.group(1).strip().strip('"').strip("'")


def resolve_design_intent(feature_dir: Path | str) -> tuple[Path, str, Path, str]:
    resolved_feature_dir = resolve_feature_dir(feature_dir)
    feature_brief = resolved_feature_dir / "feature-brief.md"
    if not feature_brief.exists():
        raise FileNotFoundError(f"缺少 feature-brief.md: {feature_brief}")

    yaml_text = "\n".join(extract_yaml_blocks(feature_brief.read_text(encoding="utf-8")))
    feature_name = extract_scalar(yaml_text, "feature_name") or resolved_feature_dir.name
    design_path = detect_latest_design_path(resolved_feature_dir)
    if not design_path.exists():
        raise FileNotFoundError(f"缺少设计文档: {design_path}")

    intent_id = f"{feature_name}-{design_path.stem}"
    return resolved_feature_dir, feature_name, design_path, intent_id


def cancel_design_intent(
    feature_dir: Path | str,
    *,
    baseline_dir: Path | None = None,
    reason: str = "",
) -> dict[str, object]:
    _, feature_name, design_path, intent_id = resolve_design_intent(feature_dir)
    design_index_path, _, _ = ensure_design_index_files(baseline_dir)
    index_data = read_index(design_index_path)

    target = next((item for item in index_data if item.get("intent_id") == intent_id), None)
    if target is None:
        return {"result": "error", "message": f"未找到设计态索引记录: {intent_id}", "index": str(design_index_path)}

    current_status = str(target.get("status") or "")
    if current_status == "CANCELLED":
        return {"result": "noop", "message": f"设计态索引已是 CANCELLED: {intent_id}", "index": str(design_index_path)}
    if current_status != "ACTIVE":
        return {
            "result": "error",
            "message": f"仅允许取消 ACTIVE 设计记录，当前状态为 {current_status or 'UNKNOWN'}: {intent_id}",
            "index": str(design_index_path),
        }

    target["status"] = "CANCELLED"
    target["cancelled_at"] = datetime.now(timezone.utc).isoformat()
    target["cancel_reason"] = reason or "developer_cancelled"
    target["cancelled_from_status"] = current_status
    write_index(design_index_path, index_data)

    return {
        "result": "cancelled",
        "intent_id": intent_id,
        "feature_name": feature_name,
        "design_version": design_path.name,
        "index": str(design_index_path),
    }


def archive_design_entries(
    *,
    baseline_dir: Path | None = None,
    feature_name: str | None = None,
    intent_id: str | None = None,
    statuses: list[str] | None = None,
    reason: str = "",
) -> dict[str, object]:
    design_index_path, _, archive_index_path = ensure_design_index_files(baseline_dir)
    index_data = read_index(design_index_path)
    archive_data = read_index(archive_index_path)

    selected_statuses = set(statuses or ARCHIVABLE_STATUSES)
    candidates = [
        item
        for item in index_data
        if (feature_name is None or item.get("feature") == feature_name)
        and (intent_id is None or item.get("intent_id") == intent_id)
        and str(item.get("status") or "") in selected_statuses
    ]

    if not candidates:
        return {
            "result": "error",
            "message": "未找到满足条件的设计索引记录可归档",
            "index": str(design_index_path),
            "archive": str(archive_index_path),
        }

    active_entries = [item for item in candidates if str(item.get("status") or "") == "ACTIVE"]
    if active_entries:
        active_intents = ", ".join(str(item.get("intent_id") or "") for item in active_entries)
        return {
            "result": "error",
            "message": f"禁止归档 ACTIVE 设计记录: {active_intents}",
            "index": str(design_index_path),
            "archive": str(archive_index_path),
        }

    remaining: list[dict[str, object]] = []
    candidate_ids = {str(item.get("intent_id") or "") for item in candidates}
    for item in index_data:
        if str(item.get("intent_id") or "") in candidate_ids:
            archived = dict(item)
            archived["archived_at"] = datetime.now(timezone.utc).isoformat()
            archived["archive_reason"] = reason or "developer_archived"
            archived["archive_source"] = DESIGN_INDEX_FILE
            archive_data.append(archived)
            continue
        remaining.append(item)

    write_index(design_index_path, remaining)
    write_index(archive_index_path, archive_data)
    return {
        "result": "archived",
        "count": len(candidates),
        "index": str(design_index_path),
        "archive": str(archive_index_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)

    p_cancel = subparsers.add_parser("cancel")
    p_cancel.add_argument("feature_dir", help="specs/<feature> 目录路径")
    p_cancel.add_argument("--reason", default="", help="取消原因")
    p_cancel.add_argument("--baseline-dir", default=None, help="baseline 目录路径")

    p_archive = subparsers.add_parser("archive")
    p_archive.add_argument("--feature-name", default=None, help="按 feature 归档")
    p_archive.add_argument("--intent-id", default=None, help="按 intent_id 归档")
    p_archive.add_argument(
        "--status",
        action="append",
        choices=["ACTIVE", "SUPERSEDED", "CANCELLED", "IMPLEMENTED"],
        default=None,
        help="仅归档指定状态，可重复传入",
    )
    p_archive.add_argument("--reason", default="", help="归档原因")
    p_archive.add_argument("--baseline-dir", default=None, help="baseline 目录路径")

    args = parser.parse_args()
    baseline_dir = Path(args.baseline_dir).resolve() if args.baseline_dir else None

    if args.action == "cancel":
        result = cancel_design_intent(args.feature_dir, baseline_dir=baseline_dir, reason=args.reason)
        if result["result"] == "cancelled":
            print("[OK] 设计态索引已取消")
            print(f"  - intent: {result['intent_id']}")
            print(f"  - index:  {result['index']}")
            return 0
        if result["result"] == "noop":
            print(f"[OK] {result['message']}")
            return 0
        print(f"[FAIL] {result['message']}")
        return 1

    if args.action == "archive":
        if not args.feature_name and not args.intent_id:
            print("[FAIL] archive 至少需要 --feature-name 或 --intent-id")
            return 1
        result = archive_design_entries(
            baseline_dir=baseline_dir,
            feature_name=args.feature_name,
            intent_id=args.intent_id,
            statuses=args.status,
            reason=args.reason,
        )
        if result["result"] == "archived":
            print("[OK] 设计态索引已归档")
            print(f"  - count:   {result['count']}")
            print(f"  - index:   {result['index']}")
            print(f"  - archive: {result['archive']}")
            return 0
        print(f"[FAIL] {result['message']}")
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
