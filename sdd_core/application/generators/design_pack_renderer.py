#!/usr/bin/env python3
"""
Render minimal design-pack files for sdd-generation.
"""

from __future__ import annotations

import re
from typing import Any


GENERIC_ENTITY_SLUGS = {"demo", "feature", "general", "oa", "office", "platform", "system", "tob"}


TAG_TO_FILES = {
    "api": ["接口契约.openapi.yaml", "接口文档.md"],
    "db-change": ["数据模型.md", "数据库变更.sql"],
    "idempotent": ["幂等策略.md"],
    "payment": ["支付状态机.md", "对账策略.md"],
    "async": ["异步事件契约.yaml"],
    "external-call": ["外部调用策略.md"],
}


def safe_slug(value: str, fallback: str = "feature") -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug or fallback


def sanitize_operation_id(summary: str, method: str, fallback: str) -> str:
    parts = [part for part in re.split(r"[^a-zA-Z0-9]+", summary) if part]
    if not parts:
        return f"{method.lower()}{fallback.title().replace('-', '')}"
    return parts[0][:1].lower() + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def feature_req_ids(requirements: list[dict[str, Any]]) -> str:
    ids = [str(item.get("req_id")) for item in requirements if item.get("req_id")]
    return "、".join(ids) if ids else "REQ-001"


def unique_preserve(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def preferred_entities(context: dict[str, Any]) -> list[str]:
    structured_prd = context["structured_prd"]
    raw_entities: list[str] = []
    for item in structured_prd.get("entities", []) or []:
        if isinstance(item, dict):
            name = str(item.get("name") or "")
        else:
            name = str(item)
        if name:
            raw_entities.append(name)
    deduped = unique_preserve(raw_entities)
    ascii_entities = [
        name
        for name in deduped
        if re.search(r"[A-Za-z]", name) and safe_slug(name, "") not in GENERIC_ENTITY_SLUGS
    ]
    if ascii_entities:
        return ascii_entities
    filtered = [name for name in deduped if safe_slug(name, "") not in GENERIC_ENTITY_SLUGS]
    return filtered or [context["feature_pascal"]]


def build_default_apis(context: dict[str, Any]) -> list[dict[str, str]]:
    structured_prd = context["structured_prd"]
    apis = []
    for item in structured_prd.get("apis", []) or []:
        if isinstance(item, dict) and item.get("path"):
            apis.append(
                {
                    "method": str(item.get("method") or "POST").upper(),
                    "path": str(item.get("path")),
                    "summary": str(item.get("summary") or item.get("path")),
                    "evidence": str(item.get("evidence") or "structured_prd"),
                }
            )
    if apis:
        return apis

    slug = context["feature_slug"]
    reqs = structured_prd.get("requirements", []) or []
    generated: list[dict[str, str]] = []
    for item in reqs[:3]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("description") or context["feature_name"])
        if any(keyword in title for keyword in ("查询", "列表", "详情")):
            generated.append({"method": "GET", "path": f"/api/v1/{slug}", "summary": title, "evidence": "fallback-from-requirement"})
        elif any(keyword in title for keyword in ("驳回", "拒绝")):
            generated.append({"method": "POST", "path": f"/api/v1/{slug}/{{id}}/reject", "summary": title, "evidence": "fallback-from-requirement"})
        elif any(keyword in title for keyword in ("审核", "审批", "通过")):
            generated.append({"method": "POST", "path": f"/api/v1/{slug}/{{id}}/review", "summary": title, "evidence": "fallback-from-requirement"})
        elif any(keyword in title for keyword in ("修改", "更新", "编辑")):
            generated.append({"method": "PUT", "path": f"/api/v1/{slug}/{{id}}", "summary": title, "evidence": "fallback-from-requirement"})
        else:
            generated.append({"method": "POST", "path": f"/api/v1/{slug}", "summary": title, "evidence": "fallback-from-requirement"})
    if generated:
        deduped: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for api in generated:
            key = (api["method"], api["path"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(api)
        return deduped

    summary = str(reqs[0].get("title") if reqs and isinstance(reqs[0], dict) else context["feature_name"])
    return [{"method": "POST", "path": f"/api/v1/{slug}", "summary": summary, "evidence": "fallback"}]


def singularize_resource(token: str) -> str:
    if token.endswith("ies") and len(token) > 3:
        return token[:-3] + "y"
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token


def extract_path_params(path: str) -> list[str]:
    return [item for item in re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", path) if item]


def last_resource_token(path: str) -> str:
    tokens = [token for token in re.split(r"[/{}/_-]+", path) if token and token not in {"api", "v1", "v2", "v3", "hr"}]
    return tokens[-1] if tokens else "resource"


def build_field(name: str, field_type: str, required: bool, description: str, location: str) -> dict[str, Any]:
    return {
        "name": name,
        "type": field_type,
        "required": required,
        "description": description,
        "location": location,
    }


def infer_request_fields(api: dict[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    method = str(api["method"]).upper()
    path = str(api["path"])
    resource_token = singularize_resource(last_resource_token(path))
    path_params = [
        build_field(param, "string", True, f"{param} 路径参数", "path")
        for param in extract_path_params(path)
    ]
    query_fields: list[dict[str, Any]] = []
    body_fields: list[dict[str, Any]] = []

    if method == "GET":
        query_fields.extend(
            [
                build_field("pageNo", "integer", False, "分页页码", "query"),
                build_field("pageSize", "integer", False, "分页大小", "query"),
            ]
        )
        if "preview" in path:
            query_fields.append(build_field("version", "string", False, "预览版本号", "query"))
        else:
            query_fields.append(build_field("keyword", "string", False, "关键字过滤条件", "query"))
        return path_params, query_fields

    body_fields.extend(
        [
            build_field("requestId", "string", True, "请求幂等标识或调用追踪标识", "body"),
            build_field("operatorId", "string", True, "操作人标识", "body"),
        ]
    )

    if "/employees" in path:
        body_fields.extend(
            [
                build_field("employeeName", "string", True, "员工姓名", "body"),
                build_field("departmentId", "string", True, "所属部门 ID", "body"),
                build_field("status", "string", False, "员工状态", "body"),
            ]
        )
    elif "/process-definitions" in path:
        body_fields.extend(
            [
                build_field("processName", "string", True, "流程名称", "body"),
                build_field("nodes", "array<object>", True, "流程节点定义列表", "body"),
            ]
        )
    elif "/leave" in path or "/overtime" in path:
        body_fields.extend(
            [
                build_field("applicantId", "string", True, "申请人 ID", "body"),
                build_field("startTime", "datetime", True, "开始时间", "body"),
                build_field("endTime", "datetime", True, "结束时间", "body"),
                build_field("reason", "string", False, "申请原因", "body"),
            ]
        )
    elif "/reimburse" in path:
        body_fields.extend(
            [
                build_field("applicantId", "string", True, "报销申请人 ID", "body"),
                build_field("amount", "number", True, "报销金额", "body"),
                build_field("reason", "string", False, "报销原因", "body"),
                build_field("attachments", "array<string>", False, "附件地址列表", "body"),
            ]
        )
    elif "/notices" in path:
        body_fields.extend(
            [
                build_field("title", "string", True, "公告标题", "body"),
                build_field("content", "string", True, "公告正文", "body"),
                build_field("publishAt", "datetime", False, "发布时间", "body"),
            ]
        )
    elif "/messages/push" in path:
        body_fields.extend(
            [
                build_field("templateCode", "string", True, "消息模板编码", "body"),
                build_field("targetUsers", "array<string>", True, "目标用户列表", "body"),
                build_field("content", "string", True, "推送内容", "body"),
            ]
        )
    else:
        body_fields.extend(
            [
                build_field(f"{resource_token}Id", "string", True, f"{resource_token} 主键标识", "body"),
                build_field("status", "string", False, "业务状态", "body"),
            ]
        )

    return path_params, body_fields


def infer_response_fields(api: dict[str, str]) -> list[dict[str, Any]]:
    method = str(api["method"]).upper()
    path = str(api["path"])
    fields = [
        build_field("code", "string", True, "业务结果码", "response"),
        build_field("message", "string", True, "结果说明", "response"),
    ]
    if method == "GET":
        if "preview" in path:
            fields.extend(
                [
                    build_field("data.previewUrl", "string", True, "在线预览地址", "response"),
                    build_field("data.fileName", "string", True, "文件名", "response"),
                ]
            )
        else:
            fields.extend(
                [
                    build_field("data.items", "array<object>", True, "结果列表", "response"),
                    build_field("data.total", "integer", True, "总记录数", "response"),
                ]
            )
        return fields

    if "/messages/push" in path:
        fields.extend(
            [
                build_field("data.messageId", "string", True, "消息记录 ID", "response"),
                build_field("data.status", "string", True, "推送状态", "response"),
            ]
        )
    elif "/process-definitions" in path:
        fields.extend(
            [
                build_field("data.processDefinitionId", "string", True, "流程定义 ID", "response"),
                build_field("data.status", "string", True, "流程定义状态", "response"),
            ]
        )
    else:
        fields.extend(
            [
                build_field("data.id", "string", True, "主记录 ID", "response"),
                build_field("data.status", "string", True, "处理后状态", "response"),
            ]
        )
    return fields


def openapi_type_parts(field_type: str) -> tuple[str, str | None]:
    mapping = {
        "string": ("string", None),
        "integer": ("integer", "int32"),
        "number": ("number", "double"),
        "datetime": ("string", "date-time"),
        "object": ("object", None),
        "array<object>": ("array", "object"),
        "array<string>": ("array", "string"),
    }
    return mapping.get(field_type, ("string", None))


def render_openapi_property(lines: list[str], field: dict[str, Any], indent: str) -> None:
    field_type = str(field["type"])
    field_name = str(field["name"]).split(".")[-1]
    openapi_type, openapi_format = openapi_type_parts(field_type)
    lines.append(f"{indent}{field_name}:")
    lines.append(f"{indent}  type: {openapi_type}")
    if openapi_type == "array":
        item_type = "object" if openapi_format == "object" else (openapi_format or "string")
        lines.append(f"{indent}  items:")
        lines.append(f"{indent}    type: {item_type}")
    elif openapi_format:
        lines.append(f"{indent}  format: {openapi_format}")
    lines.append(f"{indent}  description: {field['description']}")


def render_openapi_response_schema(lines: list[str], response_fields: list[dict[str, Any]], indent: str) -> None:
    lines.append(f"{indent}type: object")
    lines.append(f"{indent}properties:")
    top_level = [field for field in response_fields if "." not in str(field["name"])]
    nested = [field for field in response_fields if "." in str(field["name"])]
    for field in top_level:
        render_openapi_property(lines, field, indent + "  ")
    if nested:
        lines.append(f"{indent}  data:")
        lines.append(f"{indent}    type: object")
        lines.append(f"{indent}    properties:")
        for field in nested:
            render_openapi_property(lines, field, indent + "      ")


def infer_table_entries(context: dict[str, Any]) -> list[dict[str, Any]]:
    matched_tables = list(context["schema_context"]["matched_tables"])
    structured_prd = context["structured_prd"]
    entities = preferred_entities(context)
    requirements = structured_prd.get("requirements", []) or []
    req_ids = [str(item.get("req_id") or "REQ-001") for item in requirements if isinstance(item, dict)]
    req_ids_text = ", ".join(req_ids[:3]) or "REQ-001"

    entries: list[dict[str, Any]] = []
    if matched_tables:
        for index, table in enumerate(matched_tables, start=1):
            table_name = str(table.get("table_name") or f"t_{context['feature_slug'].replace('-', '_')}_{index}")
            columns = [str(col) for col in table.get("columns", []) if isinstance(col, str)] or ["id", "status", "updated_at"]
            indexed_columns = [str(col) for col in table.get("indexed_columns", []) if isinstance(col, str)]
            entity_name = entities[index - 1] if index - 1 < len(entities) else context["feature_pascal"] + str(index)
            entries.append(
                {
                    "entity": entity_name,
                    "table_name": table_name,
                    "existing_table": True,
                    "purpose": f"支撑 {entity_name} 相关需求",
                    "req_ids": req_ids_text,
                    "columns": columns,
                    "indexed_columns": indexed_columns,
                    "sql_columns": [str(col) for col in table.get("sql_columns", []) if isinstance(col, str)],
                }
            )
        return entries

    used_table_names: set[str] = set()
    for index, entity_name in enumerate(entities[:3], start=1):
        table_name = f"t_{context['feature_slug'].replace('-', '_')}_{safe_slug(entity_name, f'entity-{index}').replace('-', '_')}"
        if table_name in used_table_names:
            table_name = f"{table_name}_{index}"
        used_table_names.add(table_name)
        entries.append(
            {
                "entity": entity_name,
                "table_name": table_name,
                "existing_table": False,
                "purpose": f"新领域模式下承载 {entity_name} 数据",
                "req_ids": req_ids_text,
                "columns": ["id", "status", "created_at", "updated_at"],
                "indexed_columns": ["status"],
                "sql_columns": ["status"],
            }
        )
    return entries


def render_openapi_yaml(context: dict[str, Any]) -> str:
    apis = build_default_apis(context)
    lines = [
        "openapi: 3.0.3",
        "info:",
        f"  title: {context['feature_name']} API",
        "  version: 1.0.0",
        "paths:",
    ]
    grouped_paths: dict[str, list[dict[str, str]]] = {}
    for api in apis:
        grouped_paths.setdefault(api["path"], []).append(api)

    for path, path_apis in grouped_paths.items():
        lines.append(f"  {path}:")
        for api in path_apis:
            method = api["method"].lower()
            summary = api["summary"]
            operation_id = sanitize_operation_id(summary, api["method"], context["feature_slug"])
            path_fields, request_fields = infer_request_fields(api)
            response_fields = infer_response_fields(api)
            lines.extend(
                [
                    f"    {method}:",
                    f"      operationId: {operation_id}",
                    f"      summary: {summary}",
                ]
            )
            if path_fields or (method == "get" and request_fields):
                lines.append("      parameters:")
                for field in path_fields + ([item for item in request_fields if item["location"] == "query"] if method == "get" else []):
                    openapi_type, openapi_format = openapi_type_parts(str(field["type"]))
                    lines.extend(
                        [
                            f"        - name: {field['name']}",
                            f"          in: {field['location']}",
                            f"          required: {'true' if field['required'] else 'false'}",
                            "          schema:",
                            f"            type: {openapi_type}",
                        ]
                    )
                    if openapi_type == "array":
                        item_type = "object" if openapi_format == "object" else (openapi_format or "string")
                        lines.extend(
                            [
                                "            items:",
                                f"              type: {item_type}",
                            ]
                        )
                    elif openapi_format:
                        lines.append(f"            format: {openapi_format}")
                    lines.append(f"          description: {field['description']}")
            body_fields = [item for item in request_fields if item["location"] == "body"]
            if body_fields:
                lines.extend(
                    [
                        "      requestBody:",
                        "        required: true",
                        "        content:",
                        "          application/json:",
                        "            schema:",
                        "              type: object",
                        "              required:",
                    ]
                )
                for field in body_fields:
                    if field["required"]:
                        lines.append(f"                - {field['name']}")
                lines.append("              properties:")
                for field in body_fields:
                    render_openapi_property(lines, field, "                ")
            lines.extend(
                [
                    "      responses:",
                    "        '200':",
                    "          description: OK",
                    "          content:",
                    "            application/json:",
                    "              schema:",
                ]
            )
            render_openapi_response_schema(lines, response_fields, "                ")
    return "\n".join(lines) + "\n"


def render_interface_doc(context: dict[str, Any], design_version: str) -> str:
    structured_prd = context["structured_prd"]
    requirements = structured_prd.get("requirements", []) or []
    apis = build_default_apis(context)
    req_ids_text = feature_req_ids(requirements)
    api_rows = "\n".join(
        f"| {sanitize_operation_id(api['summary'], api['method'], context['feature_slug'])} | {api['method']} | {api['path']} | {api['summary']} | {req_ids_text} |"
        for api in apis
    )
    interface_sections: list[str] = []
    for index, api in enumerate(apis, start=1):
        operation_id = sanitize_operation_id(api["summary"], api["method"], context["feature_slug"])
        path_fields, request_fields = infer_request_fields(api)
        request_rows = "\n".join(
            f"| {field['name']} | {field['type']} | {'是' if field['required'] else '否'} | {field['description']} | {field['location']} |"
            for field in path_fields + request_fields
        ) or "| 无 | - | - | 当前接口无额外请求字段 | - |"
        response_rows = "\n".join(
            f"| {field['name']} | {field['type']} | {field['description']} | {'标准响应体字段' if field['name'] in {'code', 'message'} else '业务响应字段'} |"
            for field in infer_response_fields(api)
        ) or "| 无 | - | 当前接口无额外响应字段 | - |"
        interface_sections.append(
            "\n".join(
                [
                    f"### 4.{index} {api['method']} {api['path']}",
                    "",
                    "#### 基本信息",
                    "",
                    f"- interface_name: {operation_id}",
                    f"- method: {api['method']}",
                    f"- path: {api['path']}",
                    f"- summary: {api['summary']}",
                    f"- req_ids: {req_ids_text}",
                    "",
                    "#### 请求说明",
                    "",
                    "| 字段 | 类型 | 必填 | 含义 | 来源 |",
                    "| --- | --- | --- | --- | --- |",
                    request_rows,
                    "",
                    "#### 响应说明",
                    "",
                    "| 字段 | 类型 | 含义 | 备注 |",
                    "| --- | --- | --- | --- |",
                    response_rows,
                ]
            )
        )
    interface_detail = "\n\n".join(interface_sections)
    error_rows = "\n".join(
        [
            f"| {context['feature_slug'].upper().replace('-', '_')}_INVALID_INPUT | 400 | 参数缺失或非法 | 检查请求参数后重试 |",
            f"| {context['feature_slug'].upper().replace('-', '_')}_CONFLICT | 409 | 状态冲突或重复提交 | 刷新状态后重试 |",
        ]
    )
    dependencies = structured_prd.get("dependencies", []) or []
    dependency_text = "、".join(str(item) for item in dependencies[:3]) if dependencies else "无明确外部依赖"
    return f"""# 接口文档

## 1. 元信息
- feature_name: {context['feature_name']}
- design_version: {design_version}
- req_ids: {req_ids_text}
- 调用方: {context['feature_name']} 上游调用方
- 被调用方: {context['feature_pascal']} 所属服务

## 2. 接口清单

| 接口名 | 方法 | 路径 | 用途 | 对应 REQ-ID |
| --- | --- | --- | --- | --- |
{api_rows}

## 3. 业务说明

- 该接口解决什么业务问题：{context['structured_prd'].get('one_liner') or context['feature_name']}
- 触发时机：用户或上游系统触发本功能的主流程时
- 前置条件：REQ 范围内的输入条件满足且权限校验通过
- 后置结果：返回主流程处理结果，并为后续设计包提供可追溯接口约束

## 4. 接口详情

{interface_detail}

## 5. 错误码说明
| 错误码 | HTTP 状态 | 触发条件 | 处理建议 |
| --- | --- | --- | --- |
{error_rows}

## 6. 依赖与时序说明
- 是否依赖其他服务：{"是" if 'external-call' in context['capability_tags'] else "否"}
- 是否涉及异步回调：{"是" if 'async' in context['capability_tags'] else "否"}
- 是否需要幂等保护：{"是" if 'idempotent' in context['capability_tags'] else "否"}
- 关键依赖：{dependency_text}

## 7. 人工审阅关注点
- 接口命名是否清晰：需在评审中确认
- 路径设计是否与现有接口冲突：需结合 baseline 扫描结果确认
- 错误码是否和全局规范一致：需在评审中核对
"""
    req_ids_text = feature_req_ids(requirements)
    api_rows = "\n".join(
        f"| {sanitize_operation_id(api['summary'], api['method'], context['feature_slug'])} | {api['method']} | {api['path']} | {api['summary']} | {req_ids_text} |"
        for api in apis
    )
    request_rows_items: list[str] = []
    response_rows_items: list[str] = []
    for api in apis:
        request_fields = infer_request_fields(api)
        for field in request_fields[0] + request_fields[1]:
            request_rows_items.append(
                f"| {api['method']} {api['path']} | {field['name']} | {field['type']} | {'是' if field['required'] else '否'} | {field['description']} | {field['location']} |"
            )
        for field in infer_response_fields(api):
            response_rows_items.append(
                f"| {api['method']} {api['path']} | {field['name']} | {field['type']} | {field['description']} | {'标准响应体字段' if field['name'] in {'code', 'message'} else '业务响应字段'} |"
            )
    request_rows = "\n".join(request_rows_items)
    response_rows = "\n".join(response_rows_items)
    error_rows = "\n".join(
        [
            f"| {context['feature_slug'].upper().replace('-', '_')}_INVALID_INPUT | 400 | 参数缺失或非法 | 检查请求参数后重试 |",
            f"| {context['feature_slug'].upper().replace('-', '_')}_CONFLICT | 409 | 状态冲突或重复提交 | 刷新状态后重试 |",
        ]
    )
    dependencies = structured_prd.get("dependencies", []) or []
    dependency_text = "；".join(str(item) for item in dependencies[:3]) if dependencies else "无明确外部依赖"
    return f"""# 接口文档

## 1. 元信息

- feature_name: {context['feature_name']}
- design_version: {design_version}
- req_ids: {req_ids_text}
- 调用方: {context['feature_name']} 上游调用方
- 被调用方: {context['feature_pascal']} 所属服务

## 2. 接口清单

| 接口名 | 方法 | 路径 | 用途 | 对应 REQ-ID |
| --- | --- | --- | --- | --- |
{api_rows}

## 3. 业务说明

- 该接口解决什么业务问题：{context['structured_prd'].get('one_liner') or context['feature_name']}
- 触发时机：用户或上游系统触发本功能的主流程时
- 前置条件：REQ- 范围内的输入条件满足且权限校验通过
- 后置结果：返回主流程处理结果，并为后续设计包提供可追溯接口约束

## 4. 请求说明

| 接口 | 字段 | 类型 | 必填 | 含义 | 来源 |
| --- | --- | --- | --- | --- | --- |
{request_rows}

## 5. 响应说明

| 接口 | 字段 | 类型 | 含义 | 备注 |
| --- | --- | --- | --- | --- |
{response_rows}

## 6. 错误码说明

| 错误码 | HTTP 状态 | 触发条件 | 处理建议 |
| --- | --- | --- | --- |
{error_rows}

## 7. 依赖与时序说明

- 是否依赖其他服务：{"是" if 'external-call' in context['capability_tags'] else "否"}
- 是否涉及异步回调：{"是" if 'async' in context['capability_tags'] else "否"}
- 是否需要幂等保护：{"是" if 'idempotent' in context['capability_tags'] else "否"}
- 关键依赖：{dependency_text}

## 8. 人工审阅关注点

- 接口命名是否清晰：需在评审中确认
- 路径设计是否与现有接口冲突：需结合 baseline 扫描结果确认
- 错误码是否和全局规范一致：需在评审中核对
"""


def infer_column_type(column: str) -> str:
    if column.endswith("_time") or column.endswith("_at"):
        return "datetime"
    if column.endswith("_id") or column == "id":
        return "varchar(64)"
    if column in {"status", "type"}:
        return "varchar(32)"
    return "varchar(128)"


def render_data_model(context: dict[str, Any], design_version: str) -> str:
    requirements = context["structured_prd"].get("requirements", []) or []
    req_ids_text = feature_req_ids(requirements)
    table_entries = infer_table_entries(context)
    mapping_rows = "\n".join(
        f"| {entry['entity']} | {entry['table_name']} | {entry['purpose']} | {entry['req_ids']} |"
        for entry in table_entries
    )
    unique_columns = unique_preserve([column for entry in table_entries for column in entry["columns"]])
    field_rows = "\n".join(
        f"| {column} | {infer_column_type(column)} | 支撑 {context['feature_name']} 的 {column} 信息 | {'是' if column in {'id', 'status'} else '否'} | {'无' if column != 'status' else 'DRAFT'} |  |"
        for column in unique_columns[:10]
    )
    index_rows: list[str] = []
    for entry in table_entries:
        if entry["indexed_columns"]:
            columns_text = ",".join(entry["indexed_columns"])
            index_rows.append(
                f"| idx_{safe_slug(entry['entity'], 'entity').replace('-', '_')} | {columns_text} | 普通索引 | 支撑查询与状态过滤 |"
            )
    if not index_rows:
        index_rows.append("| idx_status | status | 普通索引 | 支撑状态过滤 |")
    return f"""# 数据模型

## 1. 元信息

- feature_name: {context['feature_name']}
- design_version: {design_version}
- req_ids: {req_ids_text}

## 2. 实体与表映射

| 实体 | 表名 | 用途 | 对应 REQ-ID |
| --- | --- | --- | --- |
{mapping_rows}

## 3. 字段清单

### 3.1 主表字段

| 字段名 | 类型 | 含义 | 是否必填 | 默认值 | 备注 |
| --- | --- | --- | --- | --- | --- |
{field_rows}

### 3.2 索引设计

| 索引名 | 字段 | 类型 | 目的 |
| --- | --- | --- | --- |
{chr(10).join(index_rows)}

## 4. 关系与约束

- 主外键关系：由主实体到扩展实体按业务关系建立
- 唯一约束：关键业务主键与状态组合需保证一致性
- 幂等约束：{"由业务幂等键保证" if 'idempotent' in context['capability_tags'] else "当前未额外声明幂等约束"}

## 5. 变更影响分析

- 对现有表的影响：{"可能涉及存量表字段/索引调整" if context['schema_context']['matched_tables'] else "当前处于待确认或新领域模式"}
- 对历史数据的影响：需评估历史数据回填与兼容策略
- 对查询性能的影响：索引设计需支撑主查询路径

## 6. 人工审阅关注点

- 字段语义是否清晰：需在评审中确认
- 索引是否过多或不足：需结合真实读写路径确认
- 是否存在模型冗余：需结合领域边界确认
"""


def render_sql(context: dict[str, Any]) -> str:
    entries = infer_table_entries(context)
    lines = ["-- UP", ""]
    for entry in entries:
        table_name = entry["table_name"]
        sql_columns = entry["sql_columns"] or entry["columns"][:3]
        if entry.get("existing_table", False):
            for column in sql_columns:
                lines.append(f"ALTER TABLE {table_name} ADD COLUMN {column} {infer_column_type(column)};")
            for index_columns in [entry["indexed_columns"]] if entry["indexed_columns"] else []:
                columns_text = ",".join(index_columns)
                index_name = f"idx_{safe_slug(entry['entity'], 'entity').replace('-', '_')}"
                lines.append(f"CREATE INDEX {index_name} ON {table_name} ({columns_text});")
        else:
            lines.append(f"CREATE TABLE {table_name} (")
            lines.append("  id varchar(64) primary key,")
            lines.append("  status varchar(32),")
            lines.append("  created_at datetime")
            lines.append(");")
    lines.extend(["", "-- DOWN", ""])
    for entry in reversed(entries):
        table_name = entry["table_name"]
        if entry.get("existing_table", False):
            lines.append(f"-- ROLLBACK for {table_name}")
            for column in reversed(entry["sql_columns"] or entry["columns"][:3]):
                lines.append(f"ALTER TABLE {table_name} DROP COLUMN {column};")
        else:
            lines.append(f"DROP TABLE {table_name};")
    return "\n".join(lines) + "\n"


def render_idempotent_strategy(context: dict[str, Any], design_version: str) -> str:
    requirements = context["structured_prd"].get("requirements", []) or []
    req_ids_text = feature_req_ids(requirements)
    apis = build_default_apis(context)
    first_api = apis[0]
    key = f"{context['feature_slug']}:{{bizId}}:{first_api['method'].lower()}"
    return f"""# 幂等策略

## 1. 元信息

- feature_name: {context['feature_name']}
- design_version: {design_version}
- req_ids: {req_ids_text}

## 2. 场景说明

- 哪些操作需要幂等：主流程写操作与重复提交敏感操作
- 为什么需要幂等：避免重复请求导致状态重复流转或数据重复写入
- 幂等失败会导致什么问题：状态不一致、重复执行、副作用放大

## 3. 幂等键设计

| 场景 | 幂等键 | 生成方式 | 生命周期 |
| --- | --- | --- | --- |
| 主流程提交 | {key} | 服务端基于业务主键与操作类型拼接 | 10 分钟 |

## 4. 冲突处理策略

- 重复请求返回什么：直接返回最近一次已确认结果
- 冲突时是否重试：否，命中幂等即停止重复执行
- 是否记录冲突事件：是，记录幂等命中日志与冲突上下文

## 5. 存储与过期策略

- 存储位置：Redis
- TTL：10 分钟
- 清理策略：自然过期

## 6. 人工审阅关注点

- 幂等键是否稳定且可复现：需在评审中确认
- TTL 是否合理：当前按短时重试场景设置
- 冲突处理是否符合业务预期：需结合业务状态机确认
"""


def render_payment_state_machine(context: dict[str, Any], design_version: str) -> str:
    requirements = context["structured_prd"].get("requirements", []) or []
    req_ids_text = feature_req_ids(requirements)
    return f"""# 支付状态机

## 1. 元信息

- feature_name: {context['feature_name']}
- design_version: {design_version}
- req_ids: {req_ids_text}

## 2. 状态列表

| 状态 | 含义 | 是否终态 | 备注 |
| --- | --- | --- | --- |
| WAIT_REVIEW | 待处理/待审核 | 否 | 初始状态 |
| SUCCESS | 处理成功 | 是 | 终态 |
| FAILED | 处理失败 | 是 | 终态 |

## 3. 状态转移

| 当前状态 | 触发事件 | 下一状态 | 条件 | 失败处理 |
| --- | --- | --- | --- | --- |
| WAIT_REVIEW | process | SUCCESS | 校验通过且事务提交成功 | 返回业务冲突错误 |
| WAIT_REVIEW | reject | FAILED | 校验失败或人工驳回 | 记录失败原因并拒绝重复执行 |

## 4. 异常与补偿

- 支付超时处理：记录超时并进入人工/补偿路径
- 回调失败处理：保留失败状态并触发补偿检查
- 补单/补偿逻辑：在对账或人工修复环节闭环

## 5. 事务边界

- 主状态切换与关键记录写入在同一事务边界内完成
- 事务边界外的异步或外部调用必须有重试/补偿说明

## 6. 人工审阅关注点

- 是否存在非法状态跳转：需在评审中确认
- 是否定义了终态：是，SUCCESS / FAILED
- 补偿逻辑是否闭环：需结合对账与人工修复策略确认
"""


def render_reconcile_strategy(context: dict[str, Any], design_version: str) -> str:
    requirements = context["structured_prd"].get("requirements", []) or []
    req_ids_text = feature_req_ids(requirements)
    return f"""# 对账策略

## 1. 元信息

- feature_name: {context['feature_name']}
- design_version: {design_version}
- req_ids: {req_ids_text}

## 2. 对账对象

- 内部账务对象：核心业务状态与关键记录
- 外部账务对象：{"外部调用结果或渠道结果" if 'external-call' in context['capability_tags'] else "当前无明确外部账务对象"}
- 对账维度：状态、时间、业务主键、处理结果

## 3. 对账频率

- 实时 / 准实时 / 日终：日终校验，关键链路可补充准实时抽样
- 调度方式：定时任务
- 失败重试方式：失败后重试并告警

## 4. 差异处理

| 差异类型 | 识别方式 | 处理策略 | 是否人工介入 |
| --- | --- | --- | --- |
| 状态不一致 | 主记录与审计记录不一致 | 生成差异记录并告警 | 是 |
| 外部结果缺失 | 外部调用或对账结果未回写 | 进入补偿与人工核查流程 | 是 |

## 5. 补偿与修复

- 自动修复逻辑：仅对可重试场景触发自动补偿
- 人工修复入口：运营/管理后台或人工审计流程
- 审计留痕：保留差异记录、补偿结果与人工操作日志

## 6. 人工审阅关注点

- 对账维度是否完整：需结合真实账务链路确认
- 差异处理是否可落地：需在评审中确认
- 是否有审计闭环：是，需保留差异与补偿记录
"""


def render_async_event_contract(context: dict[str, Any]) -> str:
    slug = context["feature_slug"].replace("-", "_")
    pascal = context["feature_pascal"]
    return f"""event: {pascal}Event
topic: TOPIC_{slug.upper()}
producer: {pascal}Service
consumer: {pascal}Consumer
payload:
  type: object
retry:
  max_attempts: 3
dlq: DLQ_{slug.upper()}
"""


def render_external_call_strategy(context: dict[str, Any], design_version: str) -> str:
    requirements = context["structured_prd"].get("requirements", []) or []
    req_ids_text = feature_req_ids(requirements)
    dependency = next(iter(context["structured_prd"].get("dependencies", []) or []), "外部系统")
    return f"""# 外部调用策略

## 1. 元信息

- feature_name: {context['feature_name']}
- design_version: {design_version}
- req_ids: {req_ids_text}

## 2. 调用关系

- 调用方：{context['feature_pascal']} 所属服务
- 被调方：{dependency}
- 调用目的：完成主流程中的外部协同处理

## 3. 超时策略

- 超时时间：2000ms
- 配置来源：服务级外部调用配置
- 超时后的业务处理：记录失败并进入重试/补偿判断

## 4. 重试策略

- 最大重试次数：3
- 重试间隔：指数退避
- 是否幂等：{"是" if 'idempotent' in context['capability_tags'] else "需结合业务确认"}

## 5. 熔断与降级

- 熔断条件：连续超时或失败率升高
- 恢复条件：健康检查恢复正常
- 降级方案：返回保守结果并触发人工/异步补偿

## 6. 监控与告警

- 监控指标：成功率、超时率、重试次数、熔断次数
- 告警阈值：失败率和超时率超过阈值立即告警
- 责任人：待指定服务负责人

## 7. 人工审阅关注点

- 重试是否会放大流量：需在评审中确认
- 降级是否可接受：需结合业务损失评估
- 告警阈值是否合理：需结合运行环境调整
"""


def build_design_pack(context: dict[str, Any], design_version: str) -> dict[str, str]:
    tags = list(context["capability_tags"])
    pack: dict[str, str] = {}
    required_files = []
    for tag in tags:
        required_files.extend(TAG_TO_FILES.get(tag, []))

    for filename in unique_preserve(required_files):
        if filename == "接口契约.openapi.yaml":
            pack[filename] = render_openapi_yaml(context)
        elif filename == "接口文档.md":
            pack[filename] = render_interface_doc(context, design_version)
        elif filename == "数据模型.md":
            pack[filename] = render_data_model(context, design_version)
        elif filename == "数据库变更.sql":
            pack[filename] = render_sql(context)
        elif filename == "幂等策略.md":
            pack[filename] = render_idempotent_strategy(context, design_version)
        elif filename == "支付状态机.md":
            pack[filename] = render_payment_state_machine(context, design_version)
        elif filename == "对账策略.md":
            pack[filename] = render_reconcile_strategy(context, design_version)
        elif filename == "异步事件契约.yaml":
            pack[filename] = render_async_event_contract(context)
        elif filename == "外部调用策略.md":
            pack[filename] = render_external_call_strategy(context, design_version)
    return pack
