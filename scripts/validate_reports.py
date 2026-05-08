#!/usr/bin/env python3
"""
validate_reports.py

校验 reports/v{N}/ 下各类报告的最小结构。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from attached_project import DEFAULT_ATTACHMENT_PATH
from json_io import read_json
from sdd_yaml import get_scalar, load_merged_yaml_mapping
from versioning import detect_latest_design_path, reports_dir_for_design, resolve_feature_dir


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / ".spec" / "schemas" / "reports"


def load_schema(name: str) -> dict:
    path = SCHEMA_DIR / name
    return read_json(path)  # type: ignore[return-value]


def validate_by_schema(value: object, schema: dict, label: str, errors: list[str]) -> None:
    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(value, dict):
            errors.append(f"{label} 不是对象")
            return
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{label} 缺少字段: {key}")
        properties = schema.get("properties", {})
        for key, child_schema in properties.items():
            if key in value:
                validate_by_schema(value[key], child_schema, f"{label}.{key}", errors)
    elif schema_type == "array":
        if not isinstance(value, list):
            errors.append(f"{label} 不是数组")
            return
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            errors.append(f"{label} 至少需要 {min_items} 项")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value, start=1):
                validate_by_schema(item, item_schema, f"{label}[{index}]", errors)
    elif schema_type == "string":
        if not isinstance(value, str):
            errors.append(f"{label} 不是字符串")
            return
        enum_values = schema.get("enum")
        if isinstance(enum_values, list) and value not in enum_values:
            errors.append(f"{label} 不在允许取值范围: {value}")
    elif schema_type == "boolean":
        if not isinstance(value, bool):
            errors.append(f"{label} 不是布尔值")
    elif schema_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"{label} 不是数值")


def resolve_path(base: Path, raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else (base / path)


def extract_risk_tier(feature_brief: Path) -> str:
    data = load_merged_yaml_mapping(feature_brief.read_text(encoding="utf-8"))
    return get_scalar(data, "risk_tier", "low") or "low"


def validate_gate_report(report_path: Path, errors: list[str], stage: str = "all") -> None:
    if not report_path.exists():
        errors.append(f"缺少 gate-report.json: {report_path}")
        return

    data = read_json(report_path)  # type: ignore[assignment]
    if not isinstance(data, dict):
        errors.append("gate-report.json 不是对象")
        return

    data_for_validation = dict(data)
    if stage == "design":
        data_for_validation.pop("gate4", None)
        data_for_validation.pop("gate5", None)
    elif stage == "implementation":
        data_for_validation.pop("gate2", None)
        data_for_validation.pop("gate3", None)

    validate_by_schema(data_for_validation, load_schema("gate-report.schema.json"), "gate-report.json", errors)

    if stage == "design":
        for gate_name in ("gate4", "gate5"):
            gate = data.get(gate_name)
            if not isinstance(gate, dict):
                continue
            if "result" not in gate:
                errors.append(f"gate-report.json.{gate_name} 缺少 result")
        return

    if stage == "implementation":
        for gate_name in ("gate2", "gate3"):
            gate = data.get(gate_name)
            if not isinstance(gate, dict):
                continue
            if "result" not in gate:
                errors.append(f"gate-report.json.{gate_name} 缺少 result")


def validate_approval(report_path: Path, errors: list[str]) -> None:
    if not report_path.exists():
        errors.append(f"缺少 approval.json: {report_path}")
        return

    data = read_json(report_path)  # type: ignore[assignment]
    validate_by_schema(data, load_schema("approval.schema.json"), "approval.json", errors)


def validate_gate4(report_path: Path, workspace_root: Path, errors: list[str]) -> None:
    if not report_path.exists():
        errors.append(f"缺少 gate4-skeleton.json: {report_path}")
        return

    data = read_json(report_path)  # type: ignore[assignment]
    validate_by_schema(data, load_schema("gate4-skeleton.schema.json"), "gate4-skeleton.json", errors)

    test_file = data.get("test_file")
    if isinstance(test_file, str):
        resolved = resolve_path(workspace_root, test_file)
        if not resolved.exists():
            errors.append(f"gate4-skeleton.json 中的 test_file 不存在: {resolved}")


def validate_verify(report_path: Path, workspace_root: Path, errors: list[str], *, risk_high: bool = False) -> None:
    if not report_path.exists():
        errors.append(f"缺少 verify-report.json: {report_path}")
        return

    data = read_json(report_path)  # type: ignore[assignment]
    validate_by_schema(data, load_schema("verify-report.schema.json"), "verify-report.json", errors)

    if isinstance(data, dict) and data.get("result") != "PASS":
        errors.append(f"verify-report.json result 必须为 PASS，当前为 {data.get('result')}: {report_path}")

    test_file = data.get("test_file")
    if isinstance(test_file, str):
        resolved = resolve_path(workspace_root, test_file)
        if not resolved.exists():
            errors.append(f"verify-report.json 中的 test_file 不存在: {resolved}")


    if risk_high and isinstance(data, dict):
        attached_execution_required = data.get("attached_execution_required")
        if attached_execution_required is not True:
            errors.append("高风险 feature 要求 verify-report.json.attached_execution_required 为 true")
        attached_execution = data.get("attached_execution")
        attached_status = attached_execution.get("status") if isinstance(attached_execution, dict) else None
        if attached_status != "PASS":
            errors.append("高风险 feature 要求 verify-report.json.attached_execution.status 为 PASS")


def validate_release_gate(report_path: Path, errors: list[str]) -> None:
    if not report_path.exists():
        return

    data = read_json(report_path)  # type: ignore[assignment]
    validate_by_schema(data, load_schema("release-gate-report.schema.json"), "release-gate-report.json", errors)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument(
        "--attachment-file",
        default=None,
        help="Optional attachment config path used to resolve relative feature paths.",
    )
    parser.add_argument("--profile", default=None, help="Optional attachment profile name.")
    parser.add_argument(
        "--stage",
        choices=["design", "implementation", "all"],
        default="all",
        help="仅校验设计阶段报告、实现阶段报告，或全部",
    )
    args = parser.parse_args(argv)

    workspace_root = ROOT
    feature_dir = resolve_feature_dir(
        args.feature_dir,
        attachment_path=Path(args.attachment_file) if args.attachment_file else DEFAULT_ATTACHMENT_PATH,
        profile=args.profile,
    )
    design_path = detect_latest_design_path(feature_dir)
    reports_dir = reports_dir_for_design(feature_dir, design_path)
    feature_brief = feature_dir / "feature-brief.md"

    if not feature_brief.exists():
        print(f"[ERROR] 缺少 feature-brief.md: {feature_brief}")
        return 1

    risk_high = extract_risk_tier(feature_brief) == "high"

    errors: list[str] = []

    if args.stage in {"design", "all"}:
        validate_gate_report(reports_dir / "gate-report.json", errors, "design")
        if risk_high:
            validate_approval(reports_dir / "approval.json", errors)

    if args.stage in {"implementation", "all"}:
        validate_gate4(reports_dir / "gate4-skeleton.json", workspace_root, errors)
        validate_verify(reports_dir / "verify-report.json", workspace_root, errors, risk_high=risk_high)
        validate_release_gate(reports_dir / "release-gate-report.json", errors)
        validate_gate_report(reports_dir / "gate-report.json", errors, "implementation")

    if errors:
        print("[FAIL] reports 结构校验失败")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("[OK] reports 结构校验通过")
    print(f"  - stage:  {args.stage}")
    print(f"  - report: {reports_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
