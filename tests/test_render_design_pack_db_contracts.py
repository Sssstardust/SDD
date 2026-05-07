from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "sdd-generation"
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from render_design_pack import infer_table_entries, render_sql  # type: ignore  # noqa: E402


def build_context() -> dict:
    return {
        "feature_name": "tob-oa-office-demo",
        "feature_slug": "tob-oa-office-demo",
        "feature_pascal": "TobOaOfficeDemo",
        "capability_tags": ["api", "async", "db-change", "security-sensitive"],
        "schema_context": {"matched_tables": []},
        "structured_prd": {
            "requirements": [
                {"req_id": "REQ-001", "priority": "P0", "title": "员工档案", "description": "员工档案维护"},
                {"req_id": "REQ-002", "priority": "P1", "title": "审批流程", "description": "请假加班报销审批"},
            ],
            "entities": [
                {"name": "ToB"},
                {"name": "审批"},
                {"name": "通知"},
                {"name": "Employee"},
                {"name": "Approval"},
                {"name": "Notice"},
            ],
            "apis": [
                {"method": "GET", "path": "/api/v1/hr/employees", "summary": "GET employees"},
                {"method": "POST", "path": "/api/v1/approvals/leave", "summary": "POST leave"},
                {"method": "POST", "path": "/api/v1/notices", "summary": "POST notices"},
            ],
        },
    }


def test_should_prefer_specific_ascii_entities_and_generate_unique_new_table_names() -> None:
    entries = infer_table_entries(build_context())

    assert [entry["entity"] for entry in entries] == ["Employee", "Approval", "Notice"]
    assert [entry["table_name"] for entry in entries] == [
        "t_tob_oa_office_demo_employee",
        "t_tob_oa_office_demo_approval",
        "t_tob_oa_office_demo_notice",
    ]


def test_should_render_create_table_sql_for_new_domain_tables_without_pending_placeholders() -> None:
    content = render_sql(build_context())

    assert "ALTER TABLE" not in content
    assert "PENDING_TABLE" not in content
    assert "CREATE TABLE t_tob_oa_office_demo_employee" in content
    assert "CREATE TABLE t_tob_oa_office_demo_approval" in content
    assert "CREATE TABLE t_tob_oa_office_demo_notice" in content
