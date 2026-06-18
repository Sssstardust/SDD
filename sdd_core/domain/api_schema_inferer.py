from __future__ import annotations
import re
from typing import Any

def sanitize_operation_id(summary: str, method: str, fallback: str) -> str:
    parts = [part for part in re.split(r"[^a-zA-Z0-9]+", summary) if part]
    if not parts:
        return f"{method.lower()}{fallback.title().replace('-', '')}"
    return parts[0][:1].lower() + "".join(part[:1].upper() + part[1:] for part in parts[1:])

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

