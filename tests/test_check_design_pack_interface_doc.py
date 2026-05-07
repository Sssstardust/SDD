from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from check_design_pack import validate_markdown_rule_file  # type: ignore  # noqa: E402


def test_should_accept_chaptered_interface_doc_layout() -> None:
    content = """# 接口文档

## 1. 元信息
- feature_name: tob-oa-office-demo
- design_version: design-v1.md
- req_ids: REQ-001
- 调用方: oa web
- 被调用方: oa service

## 2. 接口清单
| 接口名 | 方法 | 路径 | 用途 | 对应 REQ-ID |
| --- | --- | --- | --- | --- |
| gEmployees | GET | /api/v1/hr/employees | 员工查询 | REQ-001 |

## 3. 业务说明
- 该接口解决什么业务问题：员工档案查询
- 触发时机：列表页加载
- 前置条件：REQ-001 已确认
- 后置结果：返回员工列表

## 4. 接口详情

### 4.1 GET /api/v1/hr/employees

#### 基本信息
- interface_name: gEmployees
- method: GET
- path: /api/v1/hr/employees
- summary: 员工查询
- req_ids: REQ-001

#### 请求说明
| 字段 | 类型 | 必填 | 含义 | 来源 |
| --- | --- | --- | --- | --- |
| pageNo | integer | 否 | 分页页码 | query |

#### 响应说明
| 字段 | 类型 | 含义 | 备注 |
| --- | --- | --- | --- |
| data.items | array<object> | 员工列表 | 业务响应字段 |

## 5. 错误码说明
| 错误码 | HTTP 状态 | 触发条件 | 处理建议 |
| --- | --- | --- | --- |
| OA_INVALID_INPUT | 400 | 参数非法 | 检查参数后重试 |

## 6. 依赖与时序说明
- 是否依赖其他服务：否
- 是否涉及异步回调：否
- 是否需要幂等保护：否
- 关键依赖：无明确外部依赖

## 7. 人工审阅关注点
- 接口命名是否清晰：需确认
- 路径设计是否与现有接口冲突：需确认
- 错误码是否和全局规范一致：需确认
"""
    errors: list[str] = []

    validate_markdown_rule_file(Path("接口文档.md"), content, "接口文档.rules.json", errors)

    assert errors == []


def test_should_reject_interface_doc_when_chaptered_layout_lacks_request_or_response_sections() -> None:
    content = """# 接口文档

## 1. 元信息
- feature_name: tob-oa-office-demo

## 2. 接口清单
| 接口名 | 方法 | 路径 | 用途 | 对应 REQ-ID |
| --- | --- | --- | --- | --- |
| gEmployees | GET | /api/v1/hr/employees | 员工查询 | REQ-001 |

## 3. 业务说明
- REQ-001 员工档案查询

## 4. 接口详情

### 4.1 GET /api/v1/hr/employees

#### 基本信息
- interface_name: gEmployees

## 5. 错误码说明
| 错误码 | HTTP 状态 | 触发条件 | 处理建议 |
| --- | --- | --- | --- |
| OA_INVALID_INPUT | 400 | 参数非法 | 检查参数后重试 |

## 6. 依赖与时序说明
- 是否依赖其他服务：否

## 7. 人工审阅关注点
- 接口命名是否清晰：需确认
"""
    errors: list[str] = []

    validate_markdown_rule_file(Path("接口文档.md"), content, "接口文档.rules.json", errors)

    assert any("缺少请求说明" in error for error in errors)
    assert any("缺少响应说明" in error for error in errors)
