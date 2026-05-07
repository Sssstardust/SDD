#!/usr/bin/env python3
"""
Run the requirement-analyzer skill and optionally emit feature-brief.md.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib import error, request


SKILL_DIR = Path(__file__).resolve().parent
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from extract import (  # noqa: E402
    apply_overrides,
    build_heuristic_result,
    deep_merge,
    finalize_result,
    normalize_result,
    read_source,
    render_feature_brief,
    validate_structured_prd,
)


READY_EXIT_CODE = 0
SYSTEM_ERROR_EXIT_CODE = 1
CLARIFY_EXIT_CODE = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_file", help="PRD/需求文本文件路径")
    parser.add_argument("output_json", help="输出 structured-prd.json 路径")
    parser.add_argument("--feature-brief-out", default=None, help="可选：同时输出 feature-brief.md")
    parser.add_argument("--feature-name", default=None, help="手工覆盖 feature_name")
    parser.add_argument("--feature-type", default=None, help="手工覆盖 feature_type")
    parser.add_argument(
        "--project-mode",
        default=None,
        choices=["brownfield", "greenfield", "hybrid"],
        help="手工覆盖 project_mode",
    )
    parser.add_argument("--confirmed-by", default="zhangsan", help="project_mode_confirmed_by")
    parser.add_argument("--entity", action="append", default=[], help="补充实体，可重复传入")
    parser.add_argument("--api", action="append", default=[], help='补充接口，如 "POST /api/v1/orders"')
    parser.add_argument("--business-rule", action="append", default=[], help="补充业务规则，可重复传入")
    parser.add_argument("--dependency", action="append", default=[], help="补充依赖，可重复传入")
    parser.add_argument("--tag", action="append", default=[], help="补充 capability tag，可重复传入")
    parser.add_argument("--ambiguity", action="append", default=[], help="补充歧义说明，可重复传入")
    parser.add_argument("--requirement", action="append", default=[], help="补充需求描述，可重复传入")
    parser.add_argument("--overrides-file", default=None, help="JSON 文件，批量补充覆盖字段")
    parser.add_argument("--ai-only", action="store_true", help="仅允许 AI 解析，不允许启发式兜底")
    parser.add_argument("--no-ai", action="store_true", help="禁用 AI 解析，只用启发式")
    parser.add_argument("--force", action="store_true", help="允许覆盖已存在输出文件")
    return parser.parse_args()


def load_overrides_file(path: str | None) -> dict:
    if not path:
        return {}
    override_path = Path(path)
    return json.loads(override_path.read_text(encoding="utf-8"))


def build_cli_overrides(args: argparse.Namespace) -> dict:
    overrides = {
        "feature_name": args.feature_name,
        "feature_type": args.feature_type,
        "project_mode": args.project_mode,
        "project_mode_confirmed_by": args.confirmed_by,
        "entities": args.entity,
        "apis": args.api,
        "business_rules": args.business_rule,
        "dependencies": args.dependency,
        "capability_tags": args.tag,
        "ambiguities": args.ambiguity,
        "requirements": args.requirement,
        "metadata_notes": ["应用了 CLI 覆盖参数"] if any(
            [
                args.feature_name,
                args.feature_type,
                args.project_mode,
                args.entity,
                args.api,
                args.business_rule,
                args.dependency,
                args.tag,
                args.ambiguity,
                args.requirement,
                args.overrides_file,
            ]
        ) else [],
    }
    return {key: value for key, value in overrides.items() if value not in (None, [], "")}


def ai_config_from_env() -> dict[str, str] | None:
    api_key = os.environ.get("AI_GATEWAY_API_KEY")
    if not api_key:
        return None

    base_url = os.environ.get("AI_GATEWAY_BASE_URL", "https://api.openai.com/v1")
    model = os.environ.get("AI_GATEWAY_MODEL", "gpt-4.1")
    return {"api_key": api_key, "base_url": base_url.rstrip("/"), "model": model}


def render_prompt(prd_text: str, overrides: dict) -> str:
    prompt_path = SKILL_DIR / "prompt.md"
    schema_path = SKILL_DIR / "schema.json"
    template = prompt_path.read_text(encoding="utf-8")
    return (
        template.replace("{{schema}}", schema_path.read_text(encoding="utf-8"))
        .replace("{{overrides}}", json.dumps(overrides, ensure_ascii=False, indent=2))
        .replace("{{prd_content}}", prd_text)
    )


def parse_json_from_text(raw_text: str) -> dict:
    raw_text = raw_text.strip()
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(raw_text[start : end + 1])


def call_ai(prompt: str, config: dict[str, str]) -> dict:
    payload = {
        "model": config["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
    }
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url=f"{config['base_url']}/chat/completions",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['api_key']}",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=60) as response:
        body = response.read().decode("utf-8")
    parsed = json.loads(body)
    choices = parsed.get("choices") or []
    if not choices:
        raise RuntimeError("AI 响应缺少 choices")
    content = choices[0].get("message", {}).get("content")
    if not content:
        raise RuntimeError("AI 响应缺少 message.content")
    return parse_json_from_text(content)


def ensure_writable(path: Path, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"输出文件已存在，若需覆盖请使用 --force: {path}")


def main() -> int:
    args = parse_args()
    source_path = Path(args.source_file)
    output_path = Path(args.output_json)
    feature_brief_path = Path(args.feature_brief_out) if args.feature_brief_out else None

    if not source_path.exists():
        print(f"[ERROR] 源文件不存在: {source_path}")
        return SYSTEM_ERROR_EXIT_CODE

    try:
        ensure_writable(output_path, args.force)
        if feature_brief_path:
            ensure_writable(feature_brief_path, args.force)
    except FileExistsError as exc:
        print(f"[ERROR] {exc}")
        return SYSTEM_ERROR_EXIT_CODE

    try:
        prd_text = read_source(source_path)
    except Exception as exc:
        print(f"[ERROR] 读取源文件失败: {exc}")
        return SYSTEM_ERROR_EXIT_CODE

    file_overrides = load_overrides_file(args.overrides_file)
    cli_overrides = build_cli_overrides(args)
    overrides = deep_merge(file_overrides, cli_overrides)

    heuristic_result = build_heuristic_result(source_path, prd_text, args.confirmed_by)
    ai_config = None if args.no_ai else ai_config_from_env()
    ai_used = False
    ai_model = None
    merged = heuristic_result

    if ai_config:
        try:
            prompt = render_prompt(prd_text, overrides)
            ai_result = call_ai(prompt, ai_config)
            merged = deep_merge(heuristic_result, ai_result)
            ai_used = True
            ai_model = ai_config["model"]
            merged.setdefault("metadata", {})
            merged["metadata"]["notes"] = list(merged["metadata"].get("notes") or []) + ["使用 AI 提取后执行了确定性归一化"]
        except (error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
            if args.ai_only:
                print(f"[ERROR] AI 解析失败且启用了 --ai-only: {exc}")
                return SYSTEM_ERROR_EXIT_CODE
            print(f"[WARN] AI 解析失败，已回退到启发式提取: {exc}")
            merged = heuristic_result
    elif args.ai_only:
        print("[ERROR] 未检测到 AI_GATEWAY_API_KEY，无法执行 --ai-only")
        return SYSTEM_ERROR_EXIT_CODE

    normalized = normalize_result(merged, source_path, args.confirmed_by, ai_used, ai_model)
    normalized = apply_overrides(normalized, overrides)
    finalized = finalize_result(normalized)
    errors = validate_structured_prd(finalized)

    if errors:
        print("[ERROR] structured-prd 校验失败")
        for item in errors:
            print(f"  - {item}")
        return SYSTEM_ERROR_EXIT_CODE

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(finalized, ensure_ascii=False, indent=2), encoding="utf-8")

    if finalized["status"] == "clarify":
        missing_fields = finalized.get("clarify", {}).get("missing_fields", [])
        print("[CLARIFY] PRD 解析仍缺少关键信息")
        print(f"  - output: {output_path}")
        print(f"  - missing_fields: {', '.join(missing_fields)}")
        for question in finalized.get("clarify", {}).get("questions", []):
            print(f"  - question: {question}")
        return CLARIFY_EXIT_CODE

    if feature_brief_path:
        feature_brief_path.parent.mkdir(parents=True, exist_ok=True)
        feature_brief_path.write_text(render_feature_brief(finalized, source_path), encoding="utf-8")

    print("[OK] requirement-analyzer 执行完成")
    print(f"  - source: {source_path}")
    print(f"  - output: {output_path}")
    if feature_brief_path:
        print(f"  - feature_brief: {feature_brief_path}")
    print(f"  - status: {finalized['status']}")
    print(f"  - tags: {', '.join(finalized['capability_tags'])}")
    print(f"  - risk: {finalized['risk_tier']}")
    print(f"  - ai_used: {'yes' if ai_used else 'no'}")
    return READY_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main())
