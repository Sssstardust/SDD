# Feature Brief

**版本:** `v1.0`  
**日期:** `2026-04-17`  
**状态:** `Draft`

---

## 1. 基本信息

```yaml
project_mode: brownfield
project_mode_source: agent
project_mode_confidence: 0.91
project_mode_evidence:
  - "检测到现有 src/main/java"
  - "当前需求涉及支付状态流转与审核操作"
project_mode_confirmed_by: zhangsan

feature_name: payment-review-control
feature_type: payment
one_liner: "支付审核列表支持待审核支付单的查询、审核通过和驳回处理"

capability_tags:
  - api
  - payment
  - idempotent

risk_tier: high
```

---

## 2. 需求清单

```yaml
requirements:
  - req_id: REQ-001
    priority: P0
    title: "支付审核列表查询"
    description: |-
      审核人员只能查看待审核的支付单记录。
      列表页展示支付单号、订单号、支付金额、状态、提交时间、审核时间等信息。
  - req_id: REQ-002
    priority: P0
    title: "审核通过后状态流转"
    description: |-
      审核人员对待审核支付单执行审核通过操作后，支付单状态变为已通过。
      同一支付单不得重复审核。
  - req_id: REQ-003
    priority: P0
    title: "审核驳回后状态流转"
    description: |-
      审核人员对待审核支付单执行驳回操作后，支付单状态变为已驳回。
      驳回原因需要记录并可追溯。
```

---

## 3. 歧义与待澄清项

- 无

---

## 4. 业务说明

- 背景：现有支付审核操作缺少统一的审核列表和状态流转规范，需要补齐审核端能力。
- 业务目标：让审核人员对待审核支付单进行查看、审核通过、驳回，并确保状态流转可控。
- 非目标：本次不处理真实扣款通道交互，只处理审核环节。
- 成功标准：待审核支付单仅对审核人员可见，审核通过/驳回后状态准确流转，且不可重复审核。

---

## 5. 依赖与影响范围

- 涉及模块：支付管理模块、审核流程模块
- 涉及数据库：支付单主表、审核记录表（待设计确认）
- 涉及外部系统：无新增外部系统
- 是否影响现有接口：是，涉及支付审核列表查询和审核接口行为扩展

---

## 6. 风险说明

- 为什么当前 `risk_tier` 是这个级别：涉及 `payment` 标签，按规范自动判定为 `high`
- 是否需要架构审批：是
- 是否存在上线风险：有，支付单状态流转错误会影响后续资金相关业务判断

---

## 7. 审阅记录

- 审阅人：
- 审阅结论：
- 审阅时间：
