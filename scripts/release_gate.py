#!/usr/bin/env python3
"""
release_gate.py

执行上线前最小治理检查：
- Gate 5 已通过
- 回滚方案已就绪
- 监控与告警已配置
- 灰度策略已确认
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from baseline_extractors import build_design_resource_claims_for_pack, summarize_resource_claims
from baseline_paths import get_active_baseline_dir
from check_design_pack import has_rollback_statement, split_sql_migration_blocks
from concurrency import atomic_write_text, feature_lock
from design_evidence import resolve_design_pack_dir
from feature_brief import extract_affected_components
from gate_report import write_gate_section
from sdd_yaml import get_list, get_scalar, load_first_yaml_mapping
from versioning import detect_latest_design_path, reports_dir_for_design, resolve_feature_dir


TEXT_SUFFIXES = {".md", ".sql", ".yaml", ".yml", ".json", ".txt"}
ROLLBACK_KEYWORDS = ("回滚", "rollback")
MONITOR_KEYWORDS = ("监控", "monitor", "指标")
ALERT_KEYWORDS = ("告警", "alert")
GRAY_KEYWORDS = ("灰度", "canary", "白名单")
RELEASE_PLAN_NAME = "release-plan.md"


def parse_feature_meta(feature_brief: Path) -> tuple[str, list[str], str]:
    data = load_first_yaml_mapping(feature_brief.read_text(encoding="utf-8"))
    feature_name = get_scalar(data, "feature_name", feature_brief.parent.name) or feature_brief.parent.name
    tags = get_list(data, "capability_tags")
    risk_tier = (get_scalar(data, "risk_tier", "low") or "low").strip().lower()
    return feature_name, tags, risk_tier


def iter_evidence_files(feature_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in feature_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        files.append(path)
    return sorted(files)


def find_keyword_evidence(feature_dir: Path, keywords: tuple[str, ...]) -> list[str]:
    evidence: list[str] = []
    for path in iter_evidence_files(feature_dir):
        text = path.read_text(encoding="utf-8", errors="ignore")
        lowered = text.lower()
        if any(keyword.lower() in lowered for keyword in keywords):
            evidence.append(str(path))
    return evidence


def has_sql_rollback(feature_dir: Path) -> tuple[bool, list[str]]:
    evidence: list[str] = []
    for path in (feature_dir / "design-pack").glob("*.sql"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        _, down_block = split_sql_migration_blocks(text)
        if has_rollback_statement(down_block):
            evidence.append(str(path))
    return bool(evidence), evidence


def load_verify_payload(reports_dir: Path) -> tuple[dict[str, object] | None, Path]:
    verify_path = reports_dir / "verify-report.json"
    if not verify_path.exists():
        return None, verify_path
    payload = json.loads(verify_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None, verify_path


def structured_release_plan(feature_dir: Path) -> dict[str, object]:
    release_plan = feature_dir / RELEASE_PLAN_NAME
    if not release_plan.exists():
        return {"result": "MISSING", "path": str(release_plan), "checks": [], "errors": []}

    data = load_first_yaml_mapping(release_plan.read_text(encoding="utf-8"))
    checks: list[str] = []
    errors: list[str] = []

    release = data.get("release")
    if not isinstance(release, dict):
        return {"result": "MISSING", "path": str(release_plan), "checks": [], "errors": ["release-plan.md 缺少 release YAML 根节点"]}

    for key in ["owner", "approver"]:
        if get_scalar(release, key):
            checks.append(f"release {key} 已声明")
        else:
            errors.append(f"release-plan.md 缺少 {key}")

    required_ready_sections = ["rollback", "monitoring", "alerting", "rollout"]
    for section in required_ready_sections:
        section_data = release.get(section)
        if isinstance(section_data, dict) and section_data.get("ready") is True:
            checks.append(f"release {section}.ready 已确认")
        else:
            errors.append(f"release-plan.md 缺少 {section}.ready: true")

    monitoring = release.get("monitoring")
    if isinstance(monitoring, dict) and get_list(monitoring, "metrics"):
        checks.append("release monitoring.metrics 已声明")
    else:
        errors.append("release-plan.md 缺少 monitoring.metrics")

    alerting = release.get("alerting")
    if isinstance(alerting, dict) and get_list(alerting, "rules"):
        checks.append("release alerting.rules 已声明")
    else:
        errors.append("release-plan.md 缺少 alerting.rules")

    rollout = release.get("rollout")
    if isinstance(rollout, dict) and get_list(rollout, "batches"):
        checks.append("release rollout.batches 已声明")
    else:
        errors.append("release-plan.md 缺少 rollout.batches")

    return {
        "result": "PASS" if not errors else "FAIL",
        "path": str(release_plan),
        "checks": checks,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    parser.add_argument("--strict", action="store_true", help="严格模式：要求 attached execution 成功")
    args = parser.parse_args()
    strict_mode = args.strict or os.environ.get("SDD_STRICT", "").lower() in {"1", "true", "yes", "on"}

    feature_dir = resolve_feature_dir(args.feature_dir)
    feature_brief = feature_dir / "feature-brief.md"
    if not feature_brief.exists():
        print(f"[ERROR] 缺少 feature-brief.md: {feature_brief}")
        return 1

    feature_name, tags, risk_tier = parse_feature_meta(feature_brief)
    brief_content = feature_brief.read_text(encoding="utf-8")
    affected_components = extract_affected_components(brief_content)
    design_path = detect_latest_design_path(feature_dir)
    if not design_path.exists():
        print(f"[ERROR] 缺少设计文档: {design_path}")
        return 1

    reports_dir = reports_dir_for_design(feature_dir, design_path)
    design_pack_dir = resolve_design_pack_dir(feature_dir, reports_dir)
    baseline_dir = get_active_baseline_dir(create=True, migrate_legacy=True)
    schema_context_path = baseline_dir / "schema-context.json"
    schema_context: dict[str, object] = {}
    if schema_context_path.exists():
        try:
            loaded_schema_context = json.loads(schema_context_path.read_text(encoding="utf-8"))
            if isinstance(loaded_schema_context, dict):
                schema_context = loaded_schema_context
        except (OSError, json.JSONDecodeError):
            schema_context = {}
    design_resource_claims = build_design_resource_claims_for_pack(
        openapi_path=design_pack_dir / "接口契约.openapi.yaml",
        data_model_path=design_pack_dir / "数据模型.md",
        async_contract_path=design_pack_dir / "异步事件契约.yaml",
        schema_context=schema_context,
        affected_components=affected_components,
        omit_generic_tables_for_exact=False,
    )
    design_resource_claim_summary = summarize_resource_claims(design_resource_claims)
    verify_payload, verify_path = load_verify_payload(reports_dir)
    verify_result = str(verify_payload.get("result")) if isinstance(verify_payload, dict) and isinstance(verify_payload.get("result"), str) else None

    checks: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    evidence: dict[str, list[str]] = {}

    if verify_result != "PASS":
        if verify_result is None:
            errors.append(f"缺少或无法识别 verify-report.json: {verify_path}")
        else:
            errors.append(f"Gate 5 未通过，禁止执行 Release Gate: {verify_path}")
    else:
        checks.append("Gate 5 已通过，可进入上线前治理检查")

    attached_execution_required = strict_mode or risk_tier == "high"
    attached_execution_reason = "strict-mode" if strict_mode else "high-risk-feature" if risk_tier == "high" else "optional"

    if attached_execution_required:
        attached_status = None
        reported_attached_required = None
        if isinstance(verify_payload, dict):
            attached_execution = verify_payload.get("attached_execution")
            if isinstance(attached_execution, dict):
                attached_status = attached_execution.get("status")
            reported_attached_required = verify_payload.get("attached_execution_required")
        if attached_status != "PASS":
            if strict_mode:
                errors.append("严格模式要求 Gate 5 attached_execution 为 PASS")
            else:
                errors.append("高风险 feature 要求 Gate 5 attached_execution 为 PASS")
        else:
            if strict_mode:
                checks.append("严格模式 attached_execution 已通过")
            else:
                checks.append("高风险 feature attached_execution 已通过")
        if reported_attached_required is not True:
            errors.append(
                f"verify-report.json 未明确标记 attached_execution_required=true: {attached_execution_reason}"
            )

    structured_plan = structured_release_plan(feature_dir)
    structured_plan_passed = structured_plan.get("result") == "PASS"
    if structured_plan_passed:
        checks.extend(str(item) for item in structured_plan.get("checks", []))
    else:
        errors.append("缺少可通过校验的结构化 release-plan.md YAML，关键词证据不能替代上线计划")
        warnings.extend(str(item) for item in structured_plan.get("errors", []))

    rollback_evidence = find_keyword_evidence(feature_dir, ROLLBACK_KEYWORDS)
    rollback_sql_ok, rollback_sql_evidence = has_sql_rollback(feature_dir)
    if rollback_sql_evidence:
        rollback_evidence.extend(rollback_sql_evidence)
    rollback_evidence = sorted(set(rollback_evidence))
    evidence["rollback"] = rollback_evidence

    if "db-change" in tags and not rollback_sql_ok:
        errors.append("涉及 db-change，但未找到包含 DOWN/ROLLBACK 的 SQL 回滚脚本")
    elif structured_plan_passed:
        checks.append("回滚方案已就绪")
    elif rollback_evidence:
        warnings.append("发现回滚关键词证据，但结构化 release-plan.md 未通过，不能作为 PASS 依据")
    else:
        errors.append("未找到回滚方案证据")

    monitor_evidence = find_keyword_evidence(feature_dir, MONITOR_KEYWORDS)
    alert_evidence = find_keyword_evidence(feature_dir, ALERT_KEYWORDS)
    monitor_alert_evidence = sorted(set(monitor_evidence + alert_evidence))
    evidence["monitoring_alert"] = monitor_alert_evidence
    if structured_plan_passed:
        checks.append("监控与告警已配置")
    elif monitor_evidence and alert_evidence:
        warnings.append("发现监控/告警关键词证据，但结构化 release-plan.md 未通过，不能作为 PASS 依据")
    else:
        errors.append("未找到完整的监控与告警证据")

    gray_evidence = find_keyword_evidence(feature_dir, GRAY_KEYWORDS)
    evidence["gray_strategy"] = gray_evidence
    if structured_plan_passed:
        checks.append("灰度策略已确认")
    elif gray_evidence:
        warnings.append("发现灰度关键词证据，但结构化 release-plan.md 未通过，不能作为 PASS 依据")
    else:
        errors.append("未找到灰度策略证据")

    result = "PASS" if not errors else "FAIL"
    report_payload = {
        "feature_name": feature_name,
        "design_version": design_path.name,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "result": result,
        "strict": strict_mode,
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
        "evidence": evidence,
        "design_resource_claim_summary": design_resource_claim_summary,
        "design_resource_claim_highlights": design_resource_claim_summary.get("highlights", {}),
        "structured_release_plan": structured_plan,
    }

    report_path = reports_dir / "release-gate-report.json"
    reports_dir.mkdir(parents=True, exist_ok=True)
    with feature_lock(feature_dir, phase="release-gate"):
        atomic_write_text(report_path, json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_gate_section(
        reports_dir,
        gate_name="release_gate",
        feature_name=feature_name,
        design_version=design_path.name,
        payload={
            "result": result,
            "checks": checks,
            "warnings": warnings,
            "errors": errors,
            "design_resource_claim_summary": design_resource_claim_summary,
            "design_resource_claim_highlights": design_resource_claim_summary.get("highlights", {}),
            "report_file": str(report_path),
        },
    )

    if errors:
        print("[FAIL] Release Gate 检查失败")
        for err in errors:
            print(f"  - {err}")
        print(f"  - report: {report_path}")
        return 1

    print("[OK] Release Gate 检查通过")
    print(f"  - report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
