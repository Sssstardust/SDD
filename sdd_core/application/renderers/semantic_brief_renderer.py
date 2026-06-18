from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any

def infer_modules(tags: list[str]) -> str:
    modules = []
    if "api" in tags:
        modules.append("接口层")
    if "db-change" in tags:
        modules.append("数据库层")
    if "payment" in tags:
        modules.append("支付域")
    if "external-call" in tags:
        modules.append("外部系统集成")
    if "async" in tags:
        modules.append("异步事件链路")
    if "security-sensitive" in tags:
        modules.append("安全与审计")
    return "、".join(modules) if modules else "待补充"


def yaml_quote(text: str) -> str:
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_bullets(items: list[str], empty_text: str = "无") -> str:
    if not items:
        return f"- {empty_text}"
    return "\n".join(f"- {item}" for item in items)


def render_named_bullets(title_to_items: dict[str, list[str]]) -> str:
    lines: list[str] = []
    for title, items in title_to_items.items():
        content = "；".join(items) if items else "无"
        lines.append(f"- {title}：{content}")
    return "\n".join(lines)


def render_entity_bullets(entities: list[dict[str, str]]) -> str:
    if not entities:
        return "- 无明确实体映射"
    lines = []
    for entity in entities:
        name = entity.get("name") or "UNKNOWN"
        kind = entity.get("kind") or "unknown"
        evidence = entity.get("evidence") or "无证据说明"
        lines.append(f"- `{name}`（{kind}）：{evidence}")
    return "\n".join(lines)


def render_api_bullets(apis: list[dict[str, str]]) -> str:
    if not apis:
        return "- 无明确接口映射"
    lines = []
    for api in apis:
        method = api.get("method") or "CALL"
        path = api.get("path") or "UNKNOWN"
        summary = api.get("summary") or "无摘要"
        evidence = api.get("evidence") or "无证据说明"
        lines.append(f"- `{method} {path}`：{summary}；证据：{evidence}")
    return "\n".join(lines)


def render_structured_context_block(
    *,
    entities: list[dict[str, str]],
    apis: list[dict[str, str]],
    business_rules: list[str],
    dependencies: list[str],
) -> str:
    lines = ["entities:"]
    if entities:
        for entity in entities:
            lines.extend(
                [
                    f"  - name: {yaml_quote(entity.get('name') or '')}",
                    f"    kind: {yaml_quote(entity.get('kind') or '')}",
                    f"    evidence: {yaml_quote(entity.get('evidence') or '')}",
                ]
            )
    else:
        lines.append("  - {}")

    lines.append("apis:")
    if apis:
        for api in apis:
            lines.extend(
                [
                    f"  - method: {api.get('method') or 'CALL'}",
                    f"    path: {yaml_quote(api.get('path') or '')}",
                    f"    summary: {yaml_quote(api.get('summary') or '')}",
                    f"    evidence: {yaml_quote(api.get('evidence') or '')}",
                ]
            )
    else:
        lines.append("  - {}")

    lines.append("business_rules:")
    if business_rules:
        for rule in business_rules:
            lines.append(f"  - {yaml_quote(rule)}")
    else:
        lines.append('  - "无"')

    lines.append("dependencies:")
    if dependencies:
        for dependency in dependencies:
            lines.append(f"  - {yaml_quote(dependency)}")
    else:
        lines.append('  - "无"')

    return "\n".join(lines)


def summarize_requirements_by_priority(requirements: list[dict[str, str]]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {"P0": [], "P1": [], "P2": []}
    for item in requirements:
        priority = str(item.get("priority") or "P1")
        title = str(item.get("title") or item.get("description") or "需求项")
        if priority not in result:
            priority = "P1"
        result[priority].append(title)
    return result


def derive_background(
    *,
    source_path: Path,
    metadata: dict[str, Any],
    feature_type: str,
    project_mode: str,
) -> str:
    generator = "AI + 规则归一化" if metadata.get("ai_used") else "规则抽取"
    source_name = Path(str(metadata.get("source_file") or source_path)).name
    if project_mode == "greenfield":
        mode_hint = "当前按 greenfield 处理，建议在设计前先补齐 Bootstrap 约束。"
    elif project_mode == "hybrid":
        mode_hint = "当前同时存在新建与存量改造信号，建议在设计前明确边界。"
    else:
        mode_hint = "当前按 brownfield 处理，默认基于现有工程事实继续设计。"
    return f"本 Feature Brief 基于 `{source_name}` 的 structured-prd 生成，需求类型为 `{feature_type}`，生成方式为 `{generator}`。{mode_hint}"


def derive_non_goal(tags: list[str], ambiguities: list[str]) -> str:
    parts = ["PRD 未明确声明的扩展流程、额外接口和新增实体不默认纳入本轮范围。"]
    if "external-call" not in tags:
        parts.append("当前范围不默认包含新增外部系统对接。")
    if "db-change" not in tags:
        parts.append("当前范围不默认包含数据库结构调整。")
    if ambiguities:
        parts.append("所有歧义项需在进入设计前清零。")
    return " ".join(parts)


def derive_success_standard(requirements: list[dict[str, str]], apis: list[dict[str, str]], entities: list[dict[str, str]]) -> str:
    p0_titles = [str(item.get("title") or "") for item in requirements if str(item.get("priority")) == "P0"]
    summary_parts = []
    if p0_titles:
        summary_parts.append("P0 需求全部可追溯并形成设计输入：" + "；".join(p0_titles[:4]))
    if apis:
        summary_parts.append(f"关键接口映射完整（{len(apis)} 项）")
    if entities:
        summary_parts.append(f"关键实体识别完整（{len(entities)} 项）")
    return "；".join(summary_parts) if summary_parts else "待补充"


def derive_risk_reason(tags: list[str]) -> str:
    tag_set = set(tags)
    reasons: list[str] = []
    if "payment" in tag_set:
        reasons.append("命中 `payment` 标签，按规范自动判定为 `high`")
    if "async" in tag_set and "db-change" in tag_set:
        reasons.append("同时命中 `async + db-change`，按规范自动判定为 `high`")
    if "security-sensitive" in tag_set:
        reasons.append("命中 `security-sensitive`，按规范自动判定为 `high`")
    if "external-call" in tag_set and "payment" in tag_set:
        reasons.append("同时命中 `external-call + payment`，按规范自动判定为 `high`")
    if not reasons:
        reasons.append("未命中高风险组合，当前维持 `low`")
    return "；".join(reasons)


def derive_risk_focus(tags: list[str], project_mode: str) -> str:
    focus: list[str] = []
    tag_set = set(tags)
    if "db-change" in tag_set:
        focus.append("数据模型、DDL 与回滚脚本")
    if "external-call" in tag_set:
        focus.append("外部调用超时、重试与熔断")
    if "async" in tag_set:
        focus.append("消息重试、死信与消费幂等")
    if "payment" in tag_set:
        focus.append("支付状态机、对账与补偿")
    if "security-sensitive" in tag_set:
        focus.append("权限控制、审计与脱敏")
    if project_mode == "greenfield":
        focus.append("Bootstrap 约束与模块边界")
    if project_mode == "hybrid":
        focus.append("存量兼容边界与新模块边界")
    if not focus:
        focus.append("P0 需求覆盖与验收矩阵")
    return "；".join(focus)


def render_logic_atoms_yaml(logic_atoms: list[dict[str, Any]]) -> str:
    if not logic_atoms:
        return "logic_atoms: []"
    lines = ["logic_atoms:"]
    for atom in logic_atoms:
        req_id = atom.get("req_id") or "REQ-???"
        lines.append(f"  - req_id: {req_id}")
        lines.append("    logic:")
        for step_group in atom.get("logic") or []:
            comp = yaml_quote(step_group.get("component") or "Unknown")
            meth = yaml_quote(step_group.get("method") or "unknown")
            lines.append(f"      - component: {comp}")
            lines.append(f"        method: {meth}")
            lines.append("        steps:")
            for step in step_group.get("steps") or []:
                lines.append(f"          - {yaml_quote(step)}")
    return "\n".join(lines)


def render_logic_atoms_bullets(logic_atoms: list[dict[str, Any]]) -> str:
    if not logic_atoms:
        return "- 无明确逻辑建模"
    lines = []
    for atom in logic_atoms:
        req_id = atom.get("req_id") or "REQ-???"
        lines.append(f"- **{req_id}** 实现路径：")
        for step_group in atom.get("logic") or []:
            comp = step_group.get("component") or "Unknown"
            meth = step_group.get("method") or "unknown"
            steps = " -> ".join(step_group.get("steps") or [])
            lines.append(f"  - `{comp}.{meth}`: {steps}")
    return "\n".join(lines)


def render_feature_brief(data: dict[str, Any], source_path: Path) -> str:
    tags = list(data.get("capability_tags") or [])
    requirements = list(data.get("requirements") or [])
    ambiguities = list(data.get("ambiguities") or [])
    entities_payload = list(data.get("entities") or [])
    apis_payload = list(data.get("apis") or [])
    business_rules = list(data.get("business_rules") or [])
    dependencies = list(data.get("dependencies") or [])
    logic_atoms = list(data.get("logic_atoms") or [])
    metadata = dict(data.get("metadata") or {})
    project_mode = str(data.get("project_mode") or "brownfield")
    project_mode_source = str(data.get("project_mode_source") or "heuristic")
    project_mode_confidence = float(data.get("project_mode_confidence") or 0.0)
    project_mode_confirmed_by = str(data.get("project_mode_confirmed_by") or "zhangsan")
    feature_name = str(data.get("feature_name") or "auto-feature")
    feature_type = str(data.get("feature_type") or "general")
    one_liner = str(data.get("one_liner") or "待补充").replace('"', "'")
    risk_tier = str(data.get("risk_tier") or "low")
    evidence_block = "\n".join(f'  - "{item}"' for item in data.get("project_mode_evidence", []))
    tags_block = "\n".join(f"  - {tag}" for tag in tags)
    requirements_block = "\n".join(
        [
            f"  - req_id: {item['req_id']}\n"
            f"    priority: {item['priority']}\n"
            f'    title: "{item["title"]}"\n'
            f"    description: |-\n"
            + "\n".join(f"      {line}" for line in str(item["description"]).splitlines())
            for item in requirements
        ]
    )
    if ambiguities:
        ambiguity_block = "\n".join(f"- [AMBIGUOUS: {item}]" for item in ambiguities)
    else:
        ambiguity_block = "- 无"

    entities = [entity["name"] for entity in entities_payload if entity.get("name")]
    apis = [f"{api['method']} {api['path']}" for api in apis_payload if api.get("path")]

    business_goal = data.get("one_liner") or "待补充"
    background = derive_background(
        source_path=source_path,
        metadata=metadata,
        feature_type=feature_type,
        project_mode=project_mode,
    )
    non_goal = derive_non_goal(tags, ambiguities)
    success_standard = derive_success_standard(requirements, apis_payload, entities_payload)
    dependency_text = "；".join(dependencies[:4]) if dependencies else "待补充"
    requirement_priority_map = summarize_requirements_by_priority(requirements)
    business_rules_block = render_bullets(business_rules, "无明确业务规则")
    entities_block = render_entity_bullets(entities_payload)
    apis_block = render_api_bullets(apis_payload)
    dependencies_block = render_bullets(dependencies, "无明确外部依赖")
    logic_atoms_block = render_logic_atoms_bullets(logic_atoms)
    structured_context_block = render_structured_context_block(
        entities=entities_payload,
        apis=apis_payload,
        business_rules=business_rules,
        dependencies=dependencies,
    )
    logic_atoms_yaml = render_logic_atoms_yaml(logic_atoms)
    risk_reason = derive_risk_reason(tags)
    risk_focus = derive_risk_focus(tags, project_mode)
    priority_summary_block = render_named_bullets(requirement_priority_map)

    return f"""# Feature Brief

**版本:** `v1.0`  
**日期:** `{datetime.now().date()}`  
**状态:** `Draft`  

---

## 1. 基本信息

```yaml
project_mode: {project_mode}
project_mode_source: {project_mode_source}
project_mode_confidence: {project_mode_confidence:.2f}
project_mode_evidence:
{evidence_block}
project_mode_confirmed_by: {project_mode_confirmed_by}

feature_name: {feature_name}
feature_type: {feature_type}
one_liner: "{one_liner}"

capability_tags:
{tags_block}

risk_tier: {risk_tier}
```

---

## 2. 需求清单
```yaml
requirements:
{requirements_block}
```

---

## 3. 逻辑原子建模 (实现预演)
```yaml
{logic_atoms_yaml}
```

{logic_atoms_block}

---

## 4. 歧义与待澄清项
{ambiguity_block}

---

## 5. 业务说明

- 背景：{background}
- 业务目标：{business_goal}
- 非 goal：{non_goal}
- 成功标准：{success_standard}

### 5.1 需求优先级映射
{priority_summary_block}

### 5.2 关键业务规则映射
{business_rules_block}

---

## 6. 依赖与影响范围
- 涉及模块：{infer_modules(tags)}
- 涉及实体：{"、".join(entities[:6]) if entities else "待补充"}
- 涉及数据库：{"是" if "db-change" in tags else "待补充"}
- 涉及外部系统：{dependency_text}
- 是否影响现有接口：{"是" if apis else "待补充"}
- 关键接口：{"；".join(apis[:4]) if apis else "待补充"}

### 6.1 实体映射
{entities_block}

### 6.2 接口映射
{apis_block}

### 6.3 依赖映射
{dependencies_block}

### 6.4 结构化补充上下文
```yaml
{structured_context_block}
```

---

## 7. 风险说明

- 风险级别：`{risk_tier}`
- 为什么当前 `risk_tier` 是这个级别：{risk_reason}
- 是否需要架构审批：{"是" if risk_tier == "high" else "否"}
- 项目模式影响：当前 `project_mode={project_mode}`，来源 `{project_mode_source}`，置信度 `{project_mode_confidence:.2f}`。
- 设计关注点：{risk_focus}
- 是否存在上线风险：需结合详细设计和实现阶段进一步确认。

---

## 8. 审阅记录

- 审阅人：
- 审阅结论：
- 审阅时间：
"""
