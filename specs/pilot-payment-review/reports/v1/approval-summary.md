# 审批摘要：payment-review-control

- 设计版本：`design-v1.md`
- 风险级别：`high`
- 审批状态：`APPROVED`
- 一句话说明：支付审核列表支持待审核支付单的查询、审核通过和驳回处理

## 1. 需求摘要

- `REQ-001` `P0` 支付审核列表查询
- `REQ-002` `P0` 审核通过后状态流转
- `REQ-003` `P0` 审核驳回后状态流转

## 2. 核心接口

- `GET /api/v1/payments/review/pending`
- `POST /api/v1/payments/{paymentId}/approve`
- `POST /api/v1/payments/{paymentId}/reject`

## 3. 涉及表/对象

- `t_payment_order`
- `t_payment_review_record`

## 4. 门禁结果摘要

- `gate2`: `PASS`
- `gate3`: `PASS`
- `gate4`: `PASS`
- `gate5`: `PASS`

## 5. 风险与关注点

- 当前无额外风险提示

## 6. 审批建议

- 若业务风险和设计边界已确认，可将 `approval.json.status` 更新为 `APPROVED`。
- 若仍有不确定点，请在 `comments` 中补充审批意见并维持 `PENDING`。
