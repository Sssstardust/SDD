from __future__ import annotations
from typing import Any
from sdd_core.domain.design_common import feature_req_ids
from sdd_core.domain.api_schema_inferer import (
    sanitize_operation_id, openapi_type_parts, infer_request_fields,
    infer_response_fields, build_default_apis
)

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


