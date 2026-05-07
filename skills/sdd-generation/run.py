#!/usr/bin/env python3
"""
Generate design-vN.md and design-pack for an SDD feature.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from urllib import error, request


SKILL_DIR = Path(__file__).resolve().parent
ROOT = SKILL_DIR.parents[1]
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from assemble_context import assemble  # noqa: E402
from render_design_pack import build_design_pack, build_default_apis, infer_table_entries  # noqa: E402


MAX_RETRIES = 3
ESCALATION_EXIT_CODE = 3
SUPPORTED_FEEDBACK_GATES = {"gate2", "gate3", "check-design-structure", "check-design-pack", "basic-validation"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, help="feature 工作目录")
    parser.add_argument("--output", required=True, help="输出 design-vN.md 路径")
    parser.add_argument("--feedback", default=None, help="上一轮 gate-report.json 路径")
    parser.add_argument("--resume", action="store_true", help="人工修改后恢复执行")
    parser.add_argument("--force", action="store_true", help="允许覆盖已有设计文件和 design-pack")
    parser.add_argument("--no-ai", action="store_true", help="禁用 AI，直接走确定性生成")
    parser.add_argument("--ai-only", action="store_true", help="仅允许 AI 生成")
    return parser.parse_args()


def design_version_number(path: Path) -> int:
    match = re.search(r"design-v(\d+)\.md$", path.name)
    return int(match.group(1)) if match else 1


def design_version_label(path: Path) -> str:
    return f"v{design_version_number(path)}.0"


def reports_dir_for_output(path: Path) -> Path:
    return path.parent / "reports" / f"v{design_version_number(path)}"


def default_feedback_path(path: Path) -> Path:
    return reports_dir_for_output(path) / "gate-report.json"


def ai_config_from_env() -> dict[str, str] | None:
    api_key = os.environ.get("AI_GATEWAY_API_KEY")
    if not api_key:
        return None
    return {
        "api_key": api_key,
        "base_url": os.environ.get("AI_GATEWAY_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        "model": os.environ.get("AI_GATEWAY_MODEL", "gpt-4.1"),
    }


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
    req = request.Request(
        url=f"{config['base_url']}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
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


def infer_fix_hint(gate_name: str, message: str) -> str:
    if "缺少章节" in message:
        return "补齐缺失章节并保持固定编号"
    if "design-pack 引用" in message:
        return "补充 design-pack 引用并与 capability_tags 对齐"
    if "缺少 design-pack 文件" in message:
        return "按 capability_tags 生成缺失的 design-pack 文件"
    if "文件为空" in message:
        return "补齐对应设计包的最小可审阅内容"
    if "接口路径未在 OpenAPI 中找到" in message:
        return "同步设计文档接口路径与 OpenAPI 契约"
    if "表未在数据模型中声明" in message or "表未在 schema-context.json 中找到" in message:
        return "补齐数据模型表映射，并与 schema-context 保持一致"
    if "类" in message and "module-map.json" in message:
        return "改用 module-map.json 中存在的类名，或明确标记新领域模式"
    if "事务边界" in message:
        return "补充明确的事务边界说明"
    if "幂等策略" in message:
        return "补齐幂等键、冲突处理和 TTL"
    if "支付状态机" in message:
        return "补齐状态转移、事务边界和补偿说明"
    if "对账策略" in message:
        return "补齐差异处理、补偿与修复说明"
    if "外部调用策略" in message:
        return "补齐超时、重试和熔断策略"
    return "根据反馈修复对应章节或设计包内容"


def normalize_feedback_item(gate_name: str, severity: str, message: str) -> dict[str, str]:
    return {
        "gate": gate_name,
        "severity": severity,
        "message": message,
        "fix": infer_fix_hint(gate_name, message),
    }


def load_feedback_items(path: str | None, *, include_warnings: bool = True) -> list[dict[str, str]]:
    if not path:
        return []
    feedback_path = Path(path)
    if not feedback_path.exists():
        return []
    data = json.loads(feedback_path.read_text(encoding="utf-8-sig"))
    items: list[dict[str, str]] = []
    if isinstance(data, dict):
        for gate_name, payload in data.items():
            if gate_name in {"feature_name", "design_version", "updated_at"}:
                continue
            if gate_name not in SUPPORTED_FEEDBACK_GATES:
                continue
            if not isinstance(payload, dict):
                continue
            for error_item in payload.get("errors", []) or []:
                items.append(normalize_feedback_item(gate_name, "ERROR", str(error_item)))
            if include_warnings:
                for warning_item in payload.get("warnings", []) or []:
                    items.append(normalize_feedback_item(gate_name, "WARN", str(warning_item)))
    return items


def build_prompt(context: dict, feedback_items: list[dict[str, str]]) -> str:
    template = (SKILL_DIR / "prompt.md").read_text(encoding="utf-8")
    return (
        template.replace("{{context}}", json.dumps(context, ensure_ascii=False, indent=2))
        .replace("{{feedback}}", json.dumps(feedback_items, ensure_ascii=False, indent=2))
    )


def ensure_writable(path: Path, force: bool, resume: bool) -> None:
    if path.exists() and not (force or resume):
        raise FileExistsError(f"输出文件已存在，若需覆盖请使用 --force: {path}")


def load_existing_design_pack(design_pack_dir: Path) -> dict[str, str]:
    pack: dict[str, str] = {}
    if not design_pack_dir.exists():
        return pack
    for path in sorted(design_pack_dir.iterdir()):
        if path.is_file():
            pack[path.name] = path.read_text(encoding="utf-8")
    return pack


def build_generation_context(
    base_context: dict,
    *,
    output_path: Path,
    design_pack_dir: Path,
    attempt: int,
    resume: bool,
    feedback_path: Path | None,
) -> dict:
    context = deepcopy(base_context)
    context["attempt"] = attempt
    context["resume_mode"] = resume
    context["feedback_source"] = str(feedback_path) if feedback_path else None
    if resume or attempt > 1:
        if output_path.exists():
            context["current_design_markdown"] = output_path.read_text(encoding="utf-8")
        current_pack = load_existing_design_pack(design_pack_dir)
        if current_pack:
            context["current_design_pack"] = current_pack
    return context


def sanitize_design_pack(ai_pack: object, fallback_pack: dict[str, str], existing_pack: dict[str, str]) -> dict[str, str]:
    result = dict(fallback_pack)
    result.update(existing_pack)
    if not isinstance(ai_pack, dict):
        return result
    for key, value in ai_pack.items():
        if key in result and isinstance(value, str) and value.strip():
            result[key] = value
    return result


def write_design_pack(design_pack_dir: Path, pack: dict[str, str], force: bool) -> None:
    design_pack_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in pack.items():
        target = design_pack_dir / filename
        if target.exists() and not force:
            continue
        target.write_text(content, encoding="utf-8")


def choose_class(entries: list[dict], suffix: str, *, exclude_keywords: tuple[str, ...] = ()) -> dict | None:
    candidates = []
    for item in entries:
        simple_name = str(item.get("simple_name") or item.get("class_name") or "")
        if not simple_name.endswith(suffix):
            continue
        lowered = simple_name.lower()
        if any(keyword.lower() in lowered for keyword in exclude_keywords):
            continue
        candidates.append(item)
    if not candidates:
        return None
    candidates.sort(key=lambda item: len(item.get("public_methods", []) or []), reverse=True)
    return candidates[0]


def method_name(item: dict | None, prefer: tuple[str, ...] = ()) -> str | None:
    if not item:
        return None
    methods = [str(entry) for entry in item.get("public_methods", []) if isinstance(entry, str)]
    for preferred in prefer:
        for method in methods:
            if method.startswith(preferred):
                return method.split("(", 1)[0]
    if methods:
        return methods[0].split("(", 1)[0]
    return None


def build_entity_rows(context: dict) -> tuple[list[str], list[str]]:
    structured_prd = context["structured_prd"]
    schema_entries = infer_table_entries(context)
    entity_names = []
    for item in structured_prd.get("entities", []) or []:
        if isinstance(item, dict) and item.get("name"):
            entity_names.append(str(item["name"]))
    entity_names = entity_names or [entry["entity"] for entry in schema_entries]
    mapping_rows: list[str] = []
    er_entities: list[str] = []
    for index, entity in enumerate(entity_names[:4], start=1):
        table_entry = schema_entries[index - 1] if index - 1 < len(schema_entries) else schema_entries[0] if schema_entries else None
        table_name = table_entry["table_name"] if table_entry else "待确认"
        note = "来自 schema-context" if table_name.startswith("t_") else "新领域模式/待确认"
        mapping_rows.append(f"| {entity} | {entity} 相关领域对象 | {table_name} | {note} |")
        er_entities.append(str(entity).upper().replace("-", "_").replace(" ", "_"))
    if not mapping_rows:
        mapping_rows.append("| 核心实体 | 待补充 | 待确认 | 新领域模式 |")
        er_entities.append("CORE_ENTITY")
    return mapping_rows, er_entities


def render_er_diagram(entity_nodes: list[str]) -> str:
    if len(entity_nodes) == 1:
        return "erDiagram\n    " + entity_nodes[0] + " {\n        string id\n    }"
    lines = ["erDiagram"]
    primary = entity_nodes[0]
    for entity in entity_nodes[1:]:
        lines.append(f"    {primary} ||--o{{ {entity} : relates_to")
    return "\n".join(lines)


def build_sequence_section(context: dict) -> str:
    classes = list(context["module_map"]["matched_classes"])
    ui = choose_class(classes, "UI")
    controller = choose_class(classes, "Controller")
    main_service = choose_class(classes, "Service", exclude_keywords=("Permission", "Client"))
    repository = choose_class(classes, "Repository")
    state_machine = choose_class(classes, "StateMachine")

    apis = build_default_apis(context)
    primary_api = apis[0]
    service_call = method_name(
        main_service,
        prefer=("list", "query") if primary_api["method"] == "GET" else ("create", "submit", "review", "update", "approve", "reject"),
    )

    if not (ui and controller and main_service):
        return "sequenceDiagram\n    autonumber\n    Note over System: 当前为新领域模式或缺少可用存量类，详细序列待后续脚手架确认"

    ui_name = str(ui.get("simple_name") or ui.get("class_name"))
    controller_name = str(controller.get("simple_name") or controller.get("class_name"))
    service_name = str(main_service.get("simple_name") or main_service.get("class_name"))
    lines = [
        "sequenceDiagram",
        "    autonumber",
        f"    participant UI as {ui_name}",
        f"    participant C as {controller_name}",
        f"    participant S as {service_name}",
    ]
    if repository:
        repository_name = str(repository.get("simple_name") or repository.get("class_name"))
        lines.append(f"    participant R as {repository_name}")
    if state_machine:
        state_machine_name = str(state_machine.get("simple_name") or state_machine.get("class_name"))
        lines.append(f"    participant M as {state_machine_name}")

    lines.extend(
        [
            f"    UI->>C: {primary_api['method']} {primary_api['path']}",
            f"    C->>S: {(service_call + '(...)') if service_call else 'handleRequest(...)'}",
        ]
    )
    if repository:
        lines.extend(
            [
                "    S->>R: query or persist domain data",
                "    R-->>S: persistence result",
            ]
        )
    if state_machine and "payment" in context["capability_tags"]:
        lines.extend(
            [
                "    S->>M: apply state transition",
                "    M-->>S: transition accepted",
            ]
        )
    lines.extend(
        [
            "    S-->>C: domain response",
            "    C-->>UI: success / business error",
        ]
    )
    return "\n".join(lines)


def render_design_markdown(context: dict, design_version: str, design_pack_files: dict[str, str], feedback_items: list[dict[str, str]]) -> str:
    feature_name = context["feature_name"]
    feature_dir_name = context["feature_dir_name"]
    structured_prd = context["structured_prd"]
    requirements = structured_prd.get("requirements", []) or []
    req_ids = [str(item.get("req_id") or "") for item in requirements if isinstance(item, dict)][:5]
    req_ids_text = "、".join(req_ids) if req_ids else "REQ-001"
    entity_rows, er_entities = build_entity_rows(context)
    sequence_diagram = build_sequence_section(context)
    apis = build_default_apis(context)
    interface_lines = [f"- `{api['method']} {api['path']}`" for api in apis]
    db_change = "db-change" in context["capability_tags"]
    exception_rows = [
        "| 参数不合法 | 400 | 返回业务错误并提示修正输入 |",
        "| 状态冲突或重复提交 | 409 | 拒绝重复执行并返回当前状态 |",
    ]
    if "external-call" in context["capability_tags"]:
        exception_rows.append("| 外部调用超时 | 504 | 记录超时并进入重试/补偿链路 |")
    transaction_boundary = (
        "主流程写操作、状态切换与关键记录写入放在同一事务边界内。"
        if ("payment" in context["capability_tags"] or db_change)
        else "当前主流程以单次请求内的数据处理为边界。"
    )
    acceptance_rows = []
    for item in requirements:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("description") or "需求项")
        acceptance_rows.append(
            f"| {item.get('req_id', 'REQ-001')} | {title} | {title} 可通过接口或集成测试验证 | integration | {item.get('priority', 'P1')} |"
        )
    if not acceptance_rows:
        acceptance_rows.append("| REQ-001 | 主流程 | 主流程可被验证 | integration | P0 |")

    design_pack_refs = [f"- `design-pack/{name}`" for name in design_pack_files]
    feedback_note = ""
    if feedback_items:
        rendered = "\n".join(f"- [{item['gate']}] {item['message']} -> 修复建议：{item.get('fix', '按反馈修复')}" for item in feedback_items[:5])
        feedback_note = f"\n- 历史修复约束：\n{rendered}\n"

    db_overview = (
        "- 是否有表结构变更：是\n- 是否有索引变更：是\n- 是否有数据迁移：视存量数据情况评估"
        if db_change
        else "- 是否有表结构变更：否\n- 是否有索引变更：否\n- 是否有数据迁移：否"
    )

    database_ref = "引用：`design-pack/数据库变更.sql`" if "数据库变更.sql" in design_pack_files else "- 本次无独立数据库变更脚本"

    return f"""# 技术设计方案：{feature_name}

**版本:** `{design_version_label(Path(design_version))}`  
**日期:** `{date.today()}`  
**状态:** `Draft`  
**来源 Feature Brief:** `specs/{feature_dir_name}/feature-brief.md`

---

## 1. 设计概述

- 设计目标：{structured_prd.get('one_liner') or feature_name}
- 适用范围：覆盖当前 Feature 的主流程、异常处理和设计包约束。
- 对应 `REQ-ID`：{req_ids_text}
- 事务边界：{transaction_boundary}
- 设计场景：`{context['scenario']}` / `project_mode={context['project_mode']}`
{feedback_note if feedback_note else ""}
## 2. 领域模型映射

### 2.1 涉及实体

| 实体 | 说明 | 对应表/对象 | 备注 |
| --- | --- | --- | --- |
{chr(10).join(entity_rows)}

### 2.2 实体关系图

```mermaid
{render_er_diagram(er_entities)}
```

## 3. 核心流程

### 3.1 主流程序列图

```mermaid
{sequence_diagram}
```

### 3.2 异常流程

| 场景 | 触发条件 | 处理方式 |
| --- | --- | --- |
| 参数不合法 | 请求缺字段或字段非法 | 返回 400 并终止处理 |
| 状态冲突 | 请求与当前业务状态不一致 | 返回 409，避免重复流转 |
| 依赖异常 | 外部系统、数据库或关键依赖异常 | 记录错误并按策略重试/告警 |

## 4. 接口契约

引用：`design-pack/接口契约.openapi.yaml`

核心接口：

{chr(10).join(interface_lines)}

## 5. 数据库变更

### 5.1 变更概述

{db_overview}

### 5.2 变更脚本

{database_ref}

## 6. 异常处理

| 异常场景 | 错误码 | 处理策略 |
| --- | --- | --- |
{chr(10).join(exception_rows)}

## 7. 架构约束自查

- [x] 分层调用符合规范
- [x] 事务边界清晰
- [x] 异常处理符合规范
- [x] 接口契约已落盘
- [{"x" if db_change else " "}] 数据库变更有回滚

## 8. 验收标准矩阵

| REQ-ID | 需求摘要 | 验收条件（可测量） | 测试类型 | P级 |
| --- | --- | --- | --- | --- |
{chr(10).join(acceptance_rows)}

## 9. 设计包引用

{chr(10).join(design_pack_refs)}
"""


def collect_command_feedback(result: subprocess.CompletedProcess[str], gate_name: str) -> list[dict[str, str]]:
    if result.returncode == 0:
        return []
    output = (result.stdout or "") + (result.stderr or "")
    items: list[dict[str, str]] = []
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("-"):
            items.append(normalize_feedback_item(gate_name, "ERROR", stripped.lstrip("- ").strip()))
    if result.returncode != 0 and not items:
        items.append(normalize_feedback_item(gate_name, "ERROR", f"{gate_name} 执行失败但未返回结构化错误"))
    return items


def has_blocking_feedback(items: list[dict[str, str]]) -> bool:
    return any(item.get("severity") == "ERROR" for item in items)


def validate_outputs(workspace: Path, design_path: Path) -> tuple[bool, list[dict[str, str]]]:
    feature_brief = workspace / "feature-brief.md"
    commands = [
        ("check-design-structure", [sys.executable, str(ROOT / "scripts" / "check_design_structure.py"), str(design_path)]),
        ("check-design-pack", [sys.executable, str(ROOT / "scripts" / "check_design_pack.py"), str(feature_brief)]),
    ]
    feedback_items: list[dict[str, str]] = []
    for gate_name, command in commands:
        result = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
        feedback_items.extend(collect_command_feedback(result, gate_name))
    return (not has_blocking_feedback(feedback_items)), feedback_items


def run_gate_checks(workspace: Path, design_path: Path) -> tuple[bool, list[dict[str, str]], Path]:
    feedback_path = default_feedback_path(design_path)
    gate_commands = [
        [sys.executable, str(ROOT / "scripts" / "run_pipeline.py"), "gate2", str(workspace)],
        [sys.executable, str(ROOT / "scripts" / "run_pipeline.py"), "gate3", str(workspace)],
    ]
    command_feedback: list[dict[str, str]] = []
    blocking = False
    for command, gate_name in zip(gate_commands, ("gate2", "gate3")):
        result = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            blocking = True
            command_feedback.extend(collect_command_feedback(result, gate_name))

    report_feedback = load_feedback_items(str(feedback_path), include_warnings=True)
    if has_blocking_feedback(report_feedback):
        blocking = True

    combined = report_feedback or command_feedback
    if command_feedback:
        existing = {(item["gate"], item["message"]) for item in report_feedback}
        for item in command_feedback:
            key = (item["gate"], item["message"])
            if key not in existing:
                combined.append(item)
    return (not blocking), combined, feedback_path


def write_escalation_log(workspace: Path, output_path: Path, feedback_items: list[dict[str, str]], resume: bool) -> Path:
    log_path = workspace / "escalation.log"
    lines = [f"{datetime.now().astimezone().isoformat(timespec='seconds')} | {output_path.name} | 超出最大重试次数"]
    if feedback_items:
        lines.extend([f"  - [{item['gate']}] {item['message']}" for item in feedback_items[:10]])
    lines.append(
        f"  - resume_command: python {SKILL_DIR / 'run.py'} --workspace \"{workspace}\" --output \"{output_path}\" --resume --feedback \"{default_feedback_path(output_path)}\" --force"
    )
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return log_path


def generate_deterministic(
    context: dict,
    design_version: str,
    feedback_items: list[dict[str, str]],
    existing_design: str | None,
    existing_pack: dict[str, str],
    resume: bool,
) -> tuple[str, dict[str, str]]:
    design_pack = build_design_pack(context, design_version)
    if resume and existing_pack:
        merged_pack = dict(design_pack)
        merged_pack.update(existing_pack)
        design_pack = merged_pack
    if resume and existing_design:
        design_markdown = existing_design
    else:
        design_markdown = render_design_markdown(context, design_version, design_pack, feedback_items)
    return design_markdown, design_pack


def generate_with_ai(
    context: dict,
    design_version: str,
    feedback_items: list[dict[str, str]],
    config: dict[str, str],
    existing_pack: dict[str, str],
    existing_design: str | None,
) -> tuple[str, dict[str, str]]:
    prompt = build_prompt(context, feedback_items)
    payload = call_ai(prompt, config)
    fallback_pack = build_design_pack(context, design_version)
    design_markdown = str(payload.get("design_markdown") or "").strip()
    if not design_markdown:
        if existing_design:
            design_markdown = existing_design
        else:
            raise RuntimeError("AI 未返回 design_markdown")
    design_pack = sanitize_design_pack(payload.get("design_pack"), fallback_pack, existing_pack)
    return design_markdown, design_pack


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).resolve()
    output_path = Path(args.output).resolve()
    design_pack_dir = workspace / "design-pack"

    if not workspace.exists():
        print(f"[ERROR] workspace 不存在: {workspace}")
        return 1
    if not (workspace / "feature-brief.md").exists():
        print(f"[ERROR] 缺少 feature-brief.md: {workspace / 'feature-brief.md'}")
        return 1
    if args.resume and not output_path.exists():
        print(f"[ERROR] --resume 模式要求输出设计文件已存在: {output_path}")
        return 1

    try:
        ensure_writable(output_path, args.force, args.resume)
    except FileExistsError as exc:
        print(f"[ERROR] {exc}")
        return 1

    context = assemble(workspace)
    if context["errors"]:
        print("[ERROR] 上下文组装失败")
        for item in context["errors"]:
            print(f"  - {item}")
        return 1

    for item in context["warnings"]:
        print(f"[WARN] {item}")

    ai_config = None if args.no_ai else ai_config_from_env()
    if args.ai_only and not ai_config:
        print("[ERROR] 未检测到 AI_GATEWAY_API_KEY，无法执行 --ai-only")
        return 1

    feedback_path = Path(args.feedback).resolve() if args.feedback else None
    if feedback_path is None:
        candidate_feedback = default_feedback_path(output_path)
        if candidate_feedback.exists():
            feedback_path = candidate_feedback
    feedback_items = load_feedback_items(str(feedback_path) if feedback_path else None, include_warnings=True)
    design_version = output_path.name
    last_feedback_items = list(feedback_items)

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"[生成] 第 {attempt}/{MAX_RETRIES} 次尝试...")
        existing_design = output_path.read_text(encoding="utf-8") if output_path.exists() else None
        existing_pack = load_existing_design_pack(design_pack_dir)
        generation_context = build_generation_context(
            context,
            output_path=output_path,
            design_pack_dir=design_pack_dir,
            attempt=attempt,
            resume=args.resume,
            feedback_path=feedback_path,
        )
        try:
            if ai_config:
                design_markdown, design_pack = generate_with_ai(
                    generation_context,
                    design_version,
                    feedback_items,
                    ai_config,
                    existing_pack,
                    existing_design,
                )
            else:
                design_markdown, design_pack = generate_deterministic(
                    generation_context,
                    design_version,
                    feedback_items,
                    existing_design,
                    existing_pack,
                    args.resume,
                )
        except (error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
            if args.ai_only:
                print(f"[ERROR] AI 生成失败且启用了 --ai-only: {exc}")
                return 1
            print(f"[WARN] AI 生成失败，已回退到确定性生成: {exc}")
            ai_config = None
            design_markdown, design_pack = generate_deterministic(
                generation_context,
                design_version,
                feedback_items,
                existing_design,
                existing_pack,
                args.resume,
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(design_markdown, encoding="utf-8")
        write_design_pack(design_pack_dir, design_pack, args.force)

        basic_ok, basic_feedback = validate_outputs(workspace, output_path)
        if basic_ok:
            gate_ok, gate_feedback, gate_report_path = run_gate_checks(workspace, output_path)
            feedback_path = gate_report_path if gate_report_path.exists() else feedback_path
            last_feedback_items = gate_feedback
            if gate_ok:
                if any(item.get("severity") == "WARN" for item in gate_feedback):
                    for item in gate_feedback:
                        if item.get("severity") == "WARN":
                            print(f"[WARN] [{item['gate']}] {item['message']}")
                print("[OK] sdd-generation 生成完成")
                print(f"  - workspace: {workspace}")
                print(f"  - design: {output_path}")
                print(f"  - design-pack: {design_pack_dir}")
                print(f"  - tags: {', '.join(context['capability_tags'])}")
                print(f"  - scenario: {context['scenario']}")
                if feedback_path:
                    print(f"  - feedback: {feedback_path}")
                return 0

            feedback_items = [item for item in gate_feedback if item.get("severity") == "ERROR"] or gate_feedback
            print(f"[FAIL] Gate 反馈未通过，问题 {len(feedback_items)} 项")
            for item in feedback_items:
                if item.get("severity") == "ERROR":
                    print(f"  - [{item['gate']}] {item['message']}")
        else:
            feedback_items = basic_feedback
            last_feedback_items = basic_feedback
            print(f"[FAIL] 基础校验未通过，问题 {len(feedback_items)} 项")
            for item in feedback_items:
                print(f"  - [{item['gate']}] {item['message']}")

        if not ai_config:
            break

    escalation_log = write_escalation_log(workspace, output_path, last_feedback_items, args.resume)
    print(f"[ESCALATE] 超出最大重试次数（{MAX_RETRIES}），需要人工介入")
    print(f"  - escalation_log: {escalation_log}")
    if feedback_path:
        print(f"  - feedback: {feedback_path}")
    print(f"  - resume: python {SKILL_DIR / 'run.py'} --workspace \"{workspace}\" --output \"{output_path}\" --resume --feedback \"{feedback_path or default_feedback_path(output_path)}\" --force")
    return ESCALATION_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main())
