from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "requirement-analyzer"
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from extract import (  # type: ignore  # noqa: E402
    build_heuristic_result,
    detect_project_mode,
    extract_apis,
    extract_dependencies,
    extract_entities,
    finalize_result,
)


OA_TEXT = """需求：ToB 企业 OA 办公系统
背景
面向企业内部办公场景，建设统一的 OA 平台，承载基础人事信息、组织协同、审批流转、消息通知、考勤打卡与文件共享等能力。

核心功能
- 人事：员工档案、组织架构
- 审批：请假、加班、报销、流程自定义
- 公告通知、消息推送
- 日程考勤、打卡签到
- 文件网盘、在线预览

补充说明
- 面向 ToB 企业客户，需支持多角色协同使用。
- 普通成员按角色权限访问，关键操作保留审计日志。
- 审批流程需要具备一定可配置性。
"""


OA_TEXT_WITH_APIS = """需求：ToB 企业 OA 办公系统
接口草案
- GET /api/v1/hr/employees
- GET /api/v1/hr/org-tree
- POST /api/v1/approvals/process-definitions
- POST /api/v1/messages/push
"""


def test_should_not_require_apis_when_other_core_fields_are_present() -> None:
    result = finalize_result(
        {
            "feature_name": "oa-office",
            "feature_type": "general",
            "entities": [{"name": "员工", "kind": "domain-entity", "evidence": "PRD 中出现业务对象 员工"}],
            "apis": [],
            "business_rules": ["普通成员按角色权限访问，关键操作保留审计日志"],
            "requirements": [
                {
                    "req_id": "REQ-001",
                    "priority": "P0",
                    "title": "员工档案",
                    "description": "支持员工档案维护",
                }
            ],
            "ambiguities": [],
            "project_mode": "hybrid",
            "project_mode_source": "heuristic",
            "project_mode_confidence": 0.6,
            "project_mode_evidence": ["缺少明确工程上下文，默认按 hybrid 处理"],
            "project_mode_confirmed_by": "tester",
            "capability_tags": ["api"],
            "risk_tier": "low",
            "dependencies": [],
            "one_liner": "企业 OA 办公系统",
            "metadata": {},
        }
    )

    assert result["status"] == "ready"
    assert result["clarify"] is None


def test_should_use_hybrid_project_mode_when_only_sdd_workspace_context_exists() -> None:
    project_mode, evidence, confidence = detect_project_mode("ToB 企业 OA 办公需求")

    assert project_mode == "hybrid"
    assert evidence
    assert confidence < 0.8


def test_should_infer_high_risk_for_multi_domain_oa_when_security_and_data_signals_exist() -> None:
    result = build_heuristic_result(Path("oa.md"), OA_TEXT, "tester")

    assert "api" in result["capability_tags"]
    assert "async" in result["capability_tags"]
    assert "db-change" in result["capability_tags"]
    assert "security-sensitive" in result["capability_tags"]
    assert result["risk_tier"] == "high"


def test_should_use_general_feature_type_for_multi_domain_platform_demand() -> None:
    result = build_heuristic_result(Path("oa.md"), OA_TEXT, "tester")

    assert result["feature_type"] == "general"


def test_should_not_extract_false_positive_entities_or_dependencies_from_api_tokens() -> None:
    apis = extract_apis(OA_TEXT_WITH_APIS)
    entities = extract_entities(OA_TEXT_WITH_APIS, apis)
    dependencies = extract_dependencies(OA_TEXT_WITH_APIS)

    entity_names = {item["name"] for item in entities}

    assert "Tree" not in entity_names
    assert "Proces" not in entity_names
    assert "es" not in dependencies
