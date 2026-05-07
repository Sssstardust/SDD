from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "sdd-generation"
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from render_design_pack import render_interface_doc, render_openapi_yaml  # type: ignore  # noqa: E402


def build_context() -> dict:
    return {
        "feature_name": "tob-oa-office-demo",
        "feature_slug": "tob-oa-office-demo",
        "feature_pascal": "TobOaOfficeDemo",
        "capability_tags": ["api", "async", "db-change", "security-sensitive"],
        "structured_prd": {
            "one_liner": "ToB 企业 OA 办公系统",
            "requirements": [
                {"req_id": "REQ-001", "priority": "P0", "title": "员工档案", "description": "员工档案维护"},
                {"req_id": "REQ-002", "priority": "P1", "title": "公告通知", "description": "公告发布与推送"},
            ],
            "dependencies": [],
            "apis": [
                {
                    "method": "GET",
                    "path": "/api/v1/hr/employees",
                    "summary": "员工列表查询",
                    "evidence": "GET /api/v1/hr/employees",
                },
                {
                    "method": "POST",
                    "path": "/api/v1/notices",
                    "summary": "公告发布",
                    "evidence": "POST /api/v1/notices",
                },
            ],
        },
    }


def test_should_render_request_body_and_response_schema_in_openapi() -> None:
    content = render_openapi_yaml(build_context())

    assert "requestBody:" in content
    assert "application/json:" in content
    assert "- name: pageNo" in content
    assert "- name: pageSize" in content
    assert "title:" in content
    assert "content:" in content
    assert "code:" in content
    assert "data:" in content


def test_should_render_field_level_request_and_response_sections_in_interface_doc() -> None:
    content = render_interface_doc(build_context(), "design-v1.md")

    assert "| GET | /api/v1/hr/employees |" in content
    assert "| POST | /api/v1/notices |" in content
    assert "## 4. 接口详情" in content
    assert "### 4.1 GET /api/v1/hr/employees" in content
    assert "### 4.2 POST /api/v1/notices" in content
    assert "#### 请求说明" in content
    assert "#### 响应说明" in content
    assert "pageNo" in content
    assert "pageSize" in content
    assert "title" in content
    assert "content" in content
    assert "data.items" in content
    assert "data.total" in content
    assert "data.id" in content
    assert "data.status" in content
    assert "| 字段 | 类型 | 必填 | 含义 | 来源 |" in content
    assert "| 字段 | 类型 | 含义 | 备注 |" in content
    assert "| 接口 | 字段 | 类型 | 必填 | 含义 | 来源 |" not in content
