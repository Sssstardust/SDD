# 审批摘要：task-board

- 设计版本：`design-v2.md`
- 风险级别：`high`
- 审批状态：`PENDING`
- 一句话说明：小团队轻量级看板系统，支持权重排序、延迟提醒与业务审计。

## 1. 需求摘要

- `REQ-001` `P0` 任务基础 CRUD
- `REQ-002` `P0` 看板拖拽排序
- `REQ-003` `P1` 通知与到期提醒
- `REQ-004` `P1` 评论与动态记录
- `REQ-005` `P0` 权限与并发控制

## 2. 核心接口

- `POST /api/v1/task-board`

## 3. 涉及表/对象

- `t_order_pricing_relation`
- `t_tob_pricing_item`
- `t_tob_pricing_plan`

## 4. 门禁结果摘要

- `gate2`: `PASS`
- `gate3`: `PASS`

## 5. 风险与关注点

- 当前无额外风险提示

## 6. 审批建议

- 若业务风险和设计边界已确认，可将 `approval.json.status` 更新为 `APPROVED`。
- 若仍有不确定点，请在 `comments` 中补充审批意见并维持 `PENDING`。
