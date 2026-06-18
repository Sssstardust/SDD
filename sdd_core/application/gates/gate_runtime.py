#!/usr/bin/env python3
"""Application-layer gate and baseline runtime commands."""

from __future__ import annotations

from typing import Any

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sdd_core.application.gates.gate1_checker import validate_required_artifacts
from sdd_core.application.gates.gate1_reporter import build_gate1_payload
from sdd_core.application.gates.gate2_checker import build_missing_req_error, summarize_req_coverage
from sdd_core.application.gates.gate2_reporter import build_gate2_payload
from sdd_core.application.gates.gate3_checker import build_rule_modeled_ai_review, evaluate_rule_result
from sdd_core.application.gates.gate3_reporter import build_gate3_payload
from sdd_core.domain.attached_project import (
    DEFAULT_ATTACHMENT_PATH,
    load_attachment_config,
    resolve_module_map_scan_settings,
    source_signature,
)
from sdd_core.domain.language_profiles import get_language_profile
from sdd_core.infrastructure.baseline_paths import get_active_baseline_dir
from sdd_core.infrastructure.concurrency import atomic_write_text, feature_lock
from sdd_core.infrastructure.gate_report import write_gate_section
from sdd_core.infrastructure.versioning import detect_latest_design_path, reports_dir_for_design, resolve_feature_dir
from sdd_core.check_design_structure import check_structure


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _feature_paths(feature_dir: str | Path) -> tuple[Path, Path, Path, Path]:
    feature_path = resolve_feature_dir(feature_dir)
    design_path = detect_latest_design_path(feature_path)
    reports_dir = reports_dir_for_design(feature_path, design_path)
    return feature_path, feature_path / "需求规格.md", design_path, reports_dir


def _extract_req_ids(text: str) -> list[str]:
    return sorted(set(re.findall(r"\bREQ-\d+\b", text)))


def _print_result(prefix: str, report_path: Path, errors: list[str]) -> int:
    if errors:
        print(f"[FAIL] {prefix}")
        for error in errors:
            print(f"  - {error}")
        print(f"  - report: {report_path}")
        return 1
    print(f"[OK] {prefix}")
    print(f"  - report: {report_path}")
    return 0


def run_gate1(feature_dir: str | Path) -> int:
    feature_path, feature_brief, design_path, reports_dir = _feature_paths(feature_dir)
    ambiguity_tracker_path = feature_path / "ambiguity-tracker.json"
    design_pack_dir = feature_path / "design-pack"
    tracker = _read_json(ambiguity_tracker_path)
    errors = validate_required_artifacts(
        feature_brief_exists=feature_brief.exists(),
        design_exists=design_path.exists(),
        feature_brief_path=str(feature_brief),
        design_path=str(design_path),
    )
    if tracker is not None:
        from sdd_core.application.gates.gate1_checker import collect_open_ambiguity_errors

        errors.extend(collect_open_ambiguity_errors(tracker))
    warnings: list[str] = []
    if not design_pack_dir.exists():
        warnings.append(f"missing design-pack directory: {design_pack_dir}")
    payload = build_gate1_payload(
        checks=["feature-brief exists", "design document exists"] if not errors else [],
        warnings=warnings,
        errors=errors,
        commands=[],
        ambiguity_tracker=str(ambiguity_tracker_path) if ambiguity_tracker_path.exists() else None,
        design_pack_snapshot=str(design_pack_dir) if design_pack_dir.exists() else None,
        evidence={
            "feature_brief": str(feature_brief),
            "design": str(design_path),
            "design_pack": str(design_pack_dir),
        },
    )
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "gate1-report.json"
    with feature_lock(feature_path, phase="gate1"):
        atomic_write_text(report_path, json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    from sdd_core.infrastructure.gate_report import write_gate_section
    write_gate_section(
        reports_dir,
        gate_name="gate1",
        feature_name=feature_path.name,
        design_version=design_path.name,
        payload=payload,
    )
    return _print_result("Gate 1 validation completed" if not errors else "Gate 1 validation failed", report_path, errors)


def run_gate2(feature_dir: str | Path, *, strict: bool = False) -> int:
    feature_path, feature_brief, design_path, reports_dir = _feature_paths(feature_dir)
    brief_req_ids = _extract_req_ids(_read_text(feature_brief))
    design_text = _read_text(design_path)
    coverage = {req_id: [str(design_path)] if req_id in design_text else [] for req_id in brief_req_ids}
    errors: list[str] = []
    warnings: list[str] = []
    if not feature_brief.exists():
        errors.append(f"missing 需求规格.md: {feature_brief}")
    if not design_path.exists():
        errors.append(f"missing design document: {design_path}")
    if feature_brief.exists() and not brief_req_ids:
        errors.append(build_missing_req_error())
    missing = summarize_req_coverage(coverage)
    if missing:
        (errors if strict else warnings).append(f"REQ coverage missing in design: {', '.join(missing)}")
    report = {
        "status": "OK" if not errors else "FAIL",
        "checks": ["requirement ids discovered", "design requirement coverage checked"],
        "warnings": warnings,
        "errors": errors,
        "evidence": {
            "feature_brief": str(feature_brief),
            "design": str(design_path),
            "req_coverage": coverage,
        },
        "design_resource_claim_summary": {
            "highlights": {
                "req_count": len(brief_req_ids),
                "missing_req_count": len(missing),
            }
        },
    }
    payload = build_gate2_payload(report)
    report_path = write_gate_section(
        reports_dir,
        gate_name="gate2",
        feature_name=feature_path.name,
        design_version=design_path.name,
        payload=payload,
    )
    return _print_result("Gate 2 validation completed" if not errors else "Gate 2 validation failed", report_path, errors)


def detect_context_missing(feature_dir: str | Path, design_pack_dir: str | Path, baseline_dir: str | Path) -> dict[str, Any]:
    missing: list[str] = []
    feature_path = Path(feature_dir)
    pack_path = Path(design_pack_dir)
    base_path = Path(baseline_dir)
    if not feature_path.exists():
        missing.append(f"feature_dir:{feature_path}")
    if not pack_path.exists():
        missing.append(f"design_pack:{pack_path}")
    for name in ("module-map.json", "schema-context.json"):
        if not (base_path / name).exists():
            missing.append(f"baseline:{name}")
    return {
        "status": "CONTEXT_MISSING" if missing else "OK",
        "missing": missing,
    }


def run_gate3(feature_dir: str | Path) -> int:
    feature_path, _feature_brief, design_path, reports_dir = _feature_paths(feature_dir)
    errors = check_structure(design_path)
    warnings: list[str] = []
    rule_result = evaluate_rule_result(warnings=warnings, errors=errors)
    ai_review = build_rule_modeled_ai_review([])
    result = "FAIL" if errors else "PASS"
    payload = build_gate3_payload(
        result=result,
        rule_result=rule_result,
        checks=["design structure checked"],
        warnings=warnings,
        errors=errors,
        ai_review=ai_review,
    )
    report_path = write_gate_section(
        reports_dir,
        gate_name="gate3",
        feature_name=feature_path.name,
        design_version=design_path.name,
        payload=payload,
    )
    return _print_result("Gate 3 validation completed" if not errors else "Gate 3 validation failed", report_path, errors)


def _iter_source_files(scan_root: Path, extensions: tuple[str, ...]) -> list[Path]:
    if not scan_root.exists():
        return []
    files = [path for path in scan_root.rglob("*") if path.is_file()]
    if not extensions:
        return files
    return [path for path in files if path.suffix.lower() in extensions]


def refresh_module_map(
    *,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    attachment_path = Path(attachment_file) if attachment_file else DEFAULT_ATTACHMENT_PATH
    settings = resolve_module_map_scan_settings(attachment_path=attachment_path, profile=profile)
    baseline_dir = get_active_baseline_dir(
        attachment_path=attachment_path,
        profile=profile,
        create=True,
        migrate_legacy=True,
    )
    output_path = baseline_dir / "module-map.json"

    repo_root = Path(__file__).resolve().parents[3]
    project_explorer = repo_root / "mcp-servers" / "project-explorer" / "dist" / "server.js"
    if project_explorer.exists() and shutil.which("node"):
        arguments = {
            "outputPath": str(output_path),
            "scanRoots": settings.get("scan_roots", []),
        }
        result = subprocess.run(
            [
                "node",
                str(project_explorer),
                "--tool",
                "refresh_module_map",
                "--arguments",
                json.dumps(arguments, ensure_ascii=False),
            ],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0 and output_path.exists():
            print(f"[OK] module map refreshed by project-explorer: {output_path}")
            return 0
        if result.stderr.strip():
            print(f"[WARN] project-explorer refresh failed, falling back to Python scanner: {result.stderr.strip()}")

    attachment = load_attachment_config(attachment_path, profile=profile) or {}
    language = str(attachment.get("language") or "")
    language_profile = get_language_profile(language)
    scan_roots = [Path(str(item)) for item in settings.get("scan_roots", []) if isinstance(item, str)]
    classes: list[dict[str, Any]] = []
    for scan_root in scan_roots:
        root_language = language_profile
        for source_file in _iter_source_files(scan_root, root_language.source_extensions):
            text = _read_text(source_file)
            for pattern in root_language.entity_patterns:
                for match in re.finditer(pattern, text, flags=re.MULTILINE):
                    simple_name = next((group for group in reversed(match.groups()) if group), "")
                    if not simple_name:
                        continue
                    classes.append(
                        {
                            "simple_name": simple_name,
                            "name": simple_name,
                            "language": root_language.language,
                            "path": str(source_file),
                            "package": "",
                            "component_ids": [],
                        }
                    )
    payload = {
        "scanner": "sdd-core-language-profile",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "confidence": "medium" if classes else "low",
        "evidence_level": "source-scan" if classes else "empty-scan",
        "source_signature": source_signature(settings),
        "scan_settings": settings,
        "classes": classes,
        "component_ids": [],
    }
    atomic_write_text(output_path, json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] module map refreshed: {output_path}")
    print(f"  - classes: {len(classes)}")
    return 0


def refresh_schema_context(
    *,
    attachment_file: str | None = None,
    profile: str | None = None,
    from_polyquery: bool = False,
    polyquery_config: str | None = None,
    polyquery_snapshot: str | None = None,
    auto_discover: str | None = None,
    polyquery_fallback: str = "local",
) -> int:
    attachment_path = Path(attachment_file) if attachment_file else DEFAULT_ATTACHMENT_PATH
    settings = resolve_module_map_scan_settings(attachment_path=attachment_path, profile=profile)
    baseline_dir = get_active_baseline_dir(
        attachment_path=attachment_path,
        profile=profile,
        create=True,
        migrate_legacy=True,
    )
    payload = {  # type: ignore
        "source": "local-fallback",
        "requested_source": "polyquery" if from_polyquery else "local",
        "polyquery_config": polyquery_config,
        "polyquery_snapshot": polyquery_snapshot,
        "auto_discover": auto_discover,
        "polyquery_fallback": polyquery_fallback,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "confidence": "low",
        "evidence_level": "empty-local-schema",
        "source_signature": source_signature(settings),
        "tables": [],
        "component_ids": [],
    }
    output_path = baseline_dir / "schema-context.json"
    atomic_write_text(output_path, json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] schema context refreshed: {output_path}")
    return 0


def refresh_baseline_governance(
    *,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    attachment_path = Path(attachment_file) if attachment_file else DEFAULT_ATTACHMENT_PATH
    baseline_dir = get_active_baseline_dir(
        attachment_path=attachment_path,
        profile=profile,
        create=True,
        migrate_legacy=True,
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline_dir": str(baseline_dir),
        "required_files": ["module-map.json", "schema-context.json"],
    }
    output_path = baseline_dir / "baseline-governance.json"
    atomic_write_text(output_path, json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] baseline governance refreshed: {output_path}")
    return 0


def check_baseline_keys(
    *,
    attachment_file: str | None = None,
    profile: str | None = None,
) -> int:
    attachment_path = Path(attachment_file) if attachment_file else DEFAULT_ATTACHMENT_PATH
    baseline_dir = get_active_baseline_dir(
        attachment_path=attachment_path,
        profile=profile,
        create=True,
        migrate_legacy=True,
    )
    missing = [name for name in ("module-map.json", "schema-context.json") if not (baseline_dir / name).exists()]
    if missing:
        print("[FAIL] baseline key check failed")
        for name in missing:
            print(f"  - missing: {baseline_dir / name}")
        return 1
    print(f"[OK] baseline key check passed: {baseline_dir}")
    return 0
