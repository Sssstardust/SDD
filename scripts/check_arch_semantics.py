#!/usr/bin/env python3
"""
check_arch_semantics.py

Gate 3：架构语义审计最小实现。

- 检查分层 / 依赖方向
- 检查事务边界与异常处理
- 检查关键策略文档是否具备最小语义要素
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import os
from pathlib import Path

from gate_report import write_gate_section
from gates.gate3_checker import build_rule_modeled_ai_review, evaluate_rule_result
from gates.gate3_reporter import build_gate3_payload
from versioning import detect_latest_design_path, reports_dir_for_design, resolve_feature_dir


ROOT = Path(__file__).resolve().parent.parent
ARCH_STANDARD_SERVER = ROOT / "mcp-servers" / "arch-standard" / "dist" / "server.js"
DOCS_LAYERING_SEMANTICS_FILE = ROOT / "docs" / "arch-standards" / "layering-semantics.json"
MCP_LAYERING_SEMANTICS_FILE = ROOT / "mcp-servers" / "arch-standard" / "rules" / "layering-semantics.json"
REVIEW_HINT_TYPES = {
    "transaction-boundary": {
        "scope": "transaction-boundary",
        "confidence": "medium",
        "default_rationale": "Check whether transaction boundary is explicitly justified",
    },
    "layering-risk": {
        "scope": "layering-risk",
        "confidence": "medium",
        "default_rationale": "Check whether layering direction and dependency boundaries need manual review",
    },
}
GATE3_AI_REVIEW_CONFIG_FILE = ROOT / ".spec" / "gate3-ai-review.json"


def load_gate3_ai_review_command() -> list[str] | None:
    raw = os.environ.get("SDD_GATE3_AI_REVIEW_COMMAND", "").strip()
    if not raw:
        if GATE3_AI_REVIEW_CONFIG_FILE.exists():
            try:
                config_data = json.loads(GATE3_AI_REVIEW_CONFIG_FILE.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return None
            if not isinstance(config_data, dict) or config_data.get("enabled") is not True:
                return None
            data = config_data.get("command")
        else:
            return None
    else:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
    if not isinstance(data, list) or not data or not all(isinstance(item, str) and item for item in data):
        return None
    return [str(item) for item in data]


def load_gate3_ai_review_timeout_seconds() -> float:
    raw = os.environ.get("SDD_GATE3_AI_REVIEW_TIMEOUT_SECONDS", "").strip()
    if not raw and GATE3_AI_REVIEW_CONFIG_FILE.exists():
        try:
            config_data = json.loads(GATE3_AI_REVIEW_CONFIG_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            config_data = {}
        if isinstance(config_data, dict):
            raw = str(config_data.get("timeout_seconds") or "").strip()
    try:
        return float(raw) if raw else 30.0
    except ValueError:
        return 30.0


def run_gate3_ai_review_provider(
    *,
    command: list[str],
    feature_name: str,
    feature_type: str,
    tags: list[str],
    design_path: Path,
    design_text: str,
    rule_result: str,
    checks: list[str],
    warnings: list[str],
    errors: list[str],
    semantic_checks: list[dict[str, object]],
) -> dict[str, object]:
    payload = {
        "feature_name": feature_name,
        "feature_type": feature_type,
        "capability_tags": tags,
        "design_path": str(design_path),
        "design_text": design_text,
        "rule_result": rule_result,
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
        "semantic_checks": semantic_checks,
    }
    timeout = load_gate3_ai_review_timeout_seconds()
    try:
        result = subprocess.run(
            command,
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout,
            cwd=str(ROOT),
        )
    except subprocess.TimeoutExpired:
        return {
            "result": "SKIPPED",
            "mode": "provider-timeout",
            "confidence": None,
            "rationale": "AI semantic review provider timed out",
            "evidence_refs": [],
            "violations": [],
        }
    if result.returncode != 0:
        return {
            "result": "SKIPPED",
            "mode": "provider-error",
            "confidence": None,
            "rationale": "AI semantic review provider failed",
            "evidence_refs": [],
            "violations": [],
        }
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "result": "SKIPPED",
            "mode": "provider-invalid-json",
            "confidence": None,
            "rationale": "AI semantic review provider returned invalid JSON",
            "evidence_refs": [],
            "violations": [],
        }
    ai_review = data.get("ai_review") if isinstance(data, dict) and isinstance(data.get("ai_review"), dict) else data
    if not isinstance(ai_review, dict):
        return {
            "result": "SKIPPED",
            "mode": "provider-empty",
            "confidence": None,
            "rationale": "AI semantic review provider returned empty payload",
            "evidence_refs": [],
            "violations": [],
        }
    return {
        "result": str(ai_review.get("result") or "SKIPPED"),
        "mode": str(ai_review.get("mode") or "provider"),
        "confidence": ai_review.get("confidence"),
        "rationale": str(ai_review.get("rationale") or ""),
        "evidence_refs": [str(item) for item in ai_review.get("evidence_refs", []) if isinstance(item, str)],
        "violations": [
            {
                "severity": str(item.get("severity") or "warn"),
                "scope": str(item.get("scope") or "design"),
                "rationale": str(item.get("rationale") or ""),
                "confidence": str(item.get("confidence") or "medium"),
                "evidence_refs": [str(x) for x in item.get("evidence_refs", []) if isinstance(x, str)],
            }
            for item in ai_review.get("violations", [])
            if isinstance(item, dict)
        ],
    }


def extract_yaml_blocks(text: str) -> list[str]:
    matches = re.findall(r"```yaml\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return matches if matches else [text]


def extract_scalar(yaml_text: str, key: str) -> str | None:
    m = re.search(rf"(?m)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", yaml_text)
    if not m:
        return None
    return m.group(1).strip().strip('"').strip("'")


def extract_list_items(yaml_text: str, key: str) -> list[str]:
    lines = yaml_text.splitlines()
    items: list[str] = []
    in_block = False
    base_indent = 0
    for line in lines:
        if not in_block:
            if re.match(rf"^\s*{re.escape(key)}\s*:\s*$", line):
                in_block = True
                base_indent = len(line) - len(line.lstrip())
            continue
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= base_indent and not line.lstrip().startswith("- "):
            break
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip().strip('"').strip("'"))
    return items


def extract_feature_meta(feature_brief: Path) -> tuple[str, str, list[str]]:
    yaml_text = "\n".join(extract_yaml_blocks(feature_brief.read_text(encoding="utf-8")))
    feature_name = extract_scalar(yaml_text, "feature_name") or feature_brief.parent.name
    feature_type = extract_scalar(yaml_text, "feature_type") or "general"
    tags = extract_list_items(yaml_text, "capability_tags")
    return feature_name, feature_type, tags


def detect_non_empty_table_rows(design_text: str, section_title: str) -> int:
    pattern = rf"(?ms)^##\s+\d+\.\s*{re.escape(section_title)}.*?(?=^##\s+\d+\.|\Z)"
    match = re.search(pattern, design_text)
    if not match:
        return 0
    block = match.group(0)
    rows = [line for line in block.splitlines() if line.strip().startswith("|")]
    return max(len(rows) - 2, 0)


def extract_participants_and_calls(design_text: str) -> tuple[dict[str, str], list[tuple[str, str]]]:
    participants: dict[str, str] = {}
    calls: list[tuple[str, str]] = []
    in_sequence = False

    for raw_line in design_text.splitlines():
        line = raw_line.rstrip()
        if line.strip().startswith("```mermaid"):
            in_sequence = False
            continue
        if line.strip() == "sequenceDiagram":
            in_sequence = True
            continue
        if line.strip().startswith("```"):
            in_sequence = False
            continue
        if not in_sequence:
            continue

        participant_match = re.match(r"^\s*participant\s+(\w+)\s+as\s+([A-Z][A-Za-z0-9_]*)\s*$", line)
        if participant_match:
            participants[participant_match.group(1)] = participant_match.group(2)
            continue

        call_match = re.match(r"^\s*(\w+)\s*->>\s*(\w+)\s*:", line)
        if call_match:
            calls.append((call_match.group(1), call_match.group(2)))

    return participants, calls


def classify_layer(name: str) -> str:
    semantics = load_layering_semantics()
    return classify_layer_with_semantics(name, semantics)


def load_layering_semantics() -> dict[str, object]:
    fallback = {
        "layers": {
            "ui": {"suffixes": ["UI"]},
            "controller": {"suffixes": ["Controller"]},
            "service": {"suffixes": ["Service"]},
            "repository": {"suffixes": ["Repository"]},
            "state_machine": {"suffixes": ["StateMachine"]},
        },
        "direction_rules": [
            {"from": "ui", "allowed_to": ["controller"], "error": "UI 不应直接调用 {dst_name}"},
            {"from": "controller", "allowed_to": ["service", "state_machine"], "error": "Controller 不应直接调用 {dst_name}"},
            {"from": "repository", "allowed_to": [], "error": "Repository 不应作为主动调用方: {src_name} -> {dst_name}"},
            {"from": "service", "forbidden_to": ["ui"], "error": "Service 不应直接依赖 UI: {src_name} -> {dst_name}"},
            {"from": "state_machine", "forbidden_to": ["ui", "controller"], "error": "StateMachine 不应直接依赖上层: {src_name} -> {dst_name}"},
        ],
    }
    semantics_file = DOCS_LAYERING_SEMANTICS_FILE if DOCS_LAYERING_SEMANTICS_FILE.exists() else MCP_LAYERING_SEMANTICS_FILE
    if not semantics_file.exists():
        return fallback

    try:
        data = json.loads(semantics_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback

    if not isinstance(data, dict):
        return fallback
    return data


def classify_layer_with_semantics(name: str, semantics: dict[str, object]) -> str:
    layers = semantics.get("layers", {})
    if not isinstance(layers, dict):
        return "unknown"

    for layer_name, layer_config in layers.items():
        if not isinstance(layer_config, dict):
            continue
        suffixes = layer_config.get("suffixes", [])
        if not isinstance(suffixes, list):
            continue
        if any(isinstance(suffix, str) and name.endswith(suffix) for suffix in suffixes):
            return str(layer_name)
    return "unknown"


def validate_call_direction(
    participants: dict[str, str],
    calls: list[tuple[str, str]],
    semantics: dict[str, object] | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    current_semantics = semantics or load_layering_semantics()
    direction_rules = current_semantics.get("direction_rules", [])
    rule_map: dict[str, dict[str, object]] = {}
    if isinstance(direction_rules, list):
        for item in direction_rules:
            if isinstance(item, dict) and isinstance(item.get("from"), str):
                rule_map[str(item["from"])] = item

    for src_alias, dst_alias in calls:
        src_name = participants.get(src_alias, src_alias)
        dst_name = participants.get(dst_alias, dst_alias)
        src_layer = classify_layer_with_semantics(src_name, current_semantics)
        dst_layer = classify_layer_with_semantics(dst_name, current_semantics)

        if "unknown" in {src_layer, dst_layer}:
            warnings.append(f"无法识别调用分层: {src_name} -> {dst_name}")
            continue

        rule = rule_map.get(src_layer)
        if not rule:
            continue

        allowed_to = {str(item) for item in rule.get("allowed_to", []) if isinstance(item, str)}
        forbidden_to = {str(item) for item in rule.get("forbidden_to", []) if isinstance(item, str)}
        error_template = str(rule.get("error") or "调用方向不合法: {src_name} -> {dst_name}")

        if allowed_to and dst_layer not in allowed_to:
            errors.append(error_template.format(src_name=src_name, dst_name=dst_name))
            continue
        if dst_layer in forbidden_to:
            errors.append(error_template.format(src_name=src_name, dst_name=dst_name))

    return errors, warnings


def file_contains_all(path: Path, keywords: list[str]) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    return all(keyword in text for keyword in keywords)


def file_matches_requirements(path: Path, required_all: list[str], required_any_groups: list[list[str]]) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    if not all(keyword in text for keyword in required_all):
        return False
    return all(any(keyword in text for keyword in group) for group in required_any_groups)


def load_arch_feature_rules(feature_type: str, tags: list[str]) -> dict:
    if not ARCH_STANDARD_SERVER.exists():
        return {}
    payload = {
        "feature_type": feature_type,
        "capability_tags": tags,
    }
    result = subprocess.run(
        ["node", str(ARCH_STANDARD_SERVER), "--tool", "get_feature_rules", "--arguments", json.dumps(payload, ensure_ascii=False)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        return {}
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def main_for_args(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feature_dir", help="specs/<feature> 目录路径")
    args = parser.parse_args(argv)

    feature_dir = resolve_feature_dir(args.feature_dir)
    feature_brief = feature_dir / "feature-brief.md"
    if not feature_brief.exists():
        print(f"[ERROR] 缺少 feature-brief.md: {feature_brief}")
        return 1

    feature_name, feature_type, tags = extract_feature_meta(feature_brief)
    design_path = detect_latest_design_path(feature_dir)
    if not design_path.exists():
        print(f"[ERROR] 缺少设计文档: {design_path}")
        return 1

    reports_dir = reports_dir_for_design(feature_dir, design_path)
    design_text = design_path.read_text(encoding="utf-8")
    checks: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    ai_review_violations: list[dict[str, object]] = []
    arch_rules = load_arch_feature_rules(feature_type, tags)
    semantic_checks = []
    constraints = arch_rules.get("constraints", {}) if isinstance(arch_rules, dict) else {}
    if isinstance(constraints, dict):
        semantic_checks = constraints.get("semantic_checks", []) if isinstance(constraints.get("semantic_checks", []), list) else []

    participants, calls = extract_participants_and_calls(design_text)
    direction_errors, direction_warnings = validate_call_direction(participants, calls, load_layering_semantics())
    errors.extend(direction_errors)
    warnings.extend(direction_warnings)
    if not direction_errors:
        checks.append("序列图分层与依赖方向满足最小约束")

    if detect_non_empty_table_rows(design_text, "异常处理") <= 0:
        errors.append("异常处理章节缺少有效条目")
    else:
        checks.append("异常处理章节存在有效条目")

    for rule in semantic_checks:
        if not isinstance(rule, dict):
            continue
        rule_type = str(rule.get("type") or "")
        success_message = str(rule.get("successMessage") or "规则校验通过")
        error_message = str(rule.get("errorMessage") or "规则校验失败")

        if rule_type == "file_contains":
            relative_file = str(rule.get("file") or "")
            required_all = [str(item) for item in rule.get("requiredAll", []) if isinstance(item, str)]
            required_any_groups = [
                [str(keyword) for keyword in group if isinstance(keyword, str)]
                for group in rule.get("requiredAnyGroups", [])
                if isinstance(group, list)
            ]
            target_path = feature_dir / relative_file
            if file_matches_requirements(target_path, required_all, required_any_groups):
                checks.append(success_message)
            else:
                errors.append(error_message)
        elif rule_type == "design_or_file_contains":
            design_any_keywords = [str(item) for item in rule.get("designAnyKeywords", []) if isinstance(item, str)]
            fallback_file = str(rule.get("fallbackFile") or "")
            fallback_required_all = [str(item) for item in rule.get("fallbackRequiredAll", []) if isinstance(item, str)]
            has_design_signal = any(keyword in design_text for keyword in design_any_keywords)
            fallback_ok = False
            if fallback_file:
                fallback_ok = file_matches_requirements(feature_dir / fallback_file, fallback_required_all, [])
            if has_design_signal or fallback_ok:
                checks.append(success_message)
            else:
                errors.append(error_message)
        elif rule_type == "review_hint":
            hint_type = str(rule.get("hintType") or "")
            hint_meta = REVIEW_HINT_TYPES.get(hint_type, {})
            ai_review_violations.append(
                {
                    "severity": "warn",
                    "scope": str(rule.get("scope") or hint_meta.get("scope") or "design"),
                    "rationale": str(rule.get("rationale") or hint_meta.get("default_rationale") or error_message or "AI review hint"),
                    "confidence": str(rule.get("confidence") or hint_meta.get("confidence") or "medium"),
                    "evidence_refs": [str(item) for item in rule.get("evidenceRefs", []) if isinstance(item, str)],
                }
            )

    rule_result = evaluate_rule_result(warnings=warnings, errors=errors)
    ai_review = build_rule_modeled_ai_review(ai_review_violations)

    ai_review_provider_command = load_gate3_ai_review_command()
    if ai_review_provider_command:
        ai_review = run_gate3_ai_review_provider(
            command=ai_review_provider_command,
            feature_name=feature_name,
            feature_type=feature_type,
            tags=tags,
            design_path=design_path,
            design_text=design_text,
            rule_result=rule_result,
            checks=checks,
            warnings=warnings,
            errors=errors,
            semantic_checks=semantic_checks if isinstance(semantic_checks, list) else [],
        )

    result = rule_result

    report_path = write_gate_section(
        reports_dir,
        gate_name="gate3",
        feature_name=feature_name,
        design_version=design_path.name,
        payload=build_gate3_payload(
            result=result,
            rule_result=rule_result,
            checks=checks,
            warnings=warnings,
            errors=errors,
            ai_review=ai_review,
        ),
    )

    if result == "FAIL":
        print("[FAIL] Gate 3 架构语义审计失败")
        for err in errors:
            print(f"  - {err}")
        print(f"  - report: {report_path}")
        return 1

    print(f"[{result}] Gate 3 架构语义审计完成")
    for warning in warnings:
        print(f"  [WARN] {warning}")
    print(f"  - report: {report_path}")
    return 0

def main() -> int:
    return main_for_args()


if __name__ == "__main__":
    raise SystemExit(main())
