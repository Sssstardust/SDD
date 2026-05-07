# Release Plan

```yaml
release:
  owner: payment-review-team
  approver: tech-lead
  rollback:
    ready: true
    trigger: "audit_api_error_rate_gt_1_percent_or_state_inconsistent"
    sql_down_confirmed: true
  monitoring:
    ready: true
    metrics:
      - payment_review_list_success_rate
      - payment_review_approve_success_rate
      - payment_review_reject_success_rate
      - payment_review_api_p95_latency
  alerting:
    ready: true
    rules:
      - payment_review_api_error_rate_high
      - payment_review_duplicate_review_conflict_spike
      - payment_review_state_inconsistent
  rollout:
    ready: true
    batches:
      - "white-list reviewers"
      - "all reviewer role"
```

## 1. 回滚方案

- 应用回滚：支付审核列表、审核通过和审核驳回逻辑通过独立发布包回退到上一个稳定版本。
- 数据回滚：本试点不涉及 DDL 变更；若上线后出现状态流转异常，回滚应用后按审核记录恢复支付单状态。
- 操作回滚：若审核流转或权限校验异常，立即关闭新审核入口，回退应用版本，并按审核记录核对 `WAIT_REVIEW / APPROVED / REJECTED` 状态。

## 2. 监控与告警

- 监控指标：
  - 支付审核列表查询成功率与 P95 响应时间
  - 审核通过接口成功率与重复审核拒绝次数
  - 审核驳回接口成功率与驳回原因缺失次数
- 告警规则：
  - 审核接口 5 分钟错误率超过 1% 时触发告警
  - 重复审核冲突量异常升高时触发告警并通知审核值班人员
  - 审核驳回接口出现连续失败或状态不一致时触发告警

## 3. 灰度策略

- 灰度阶段 1：先对白名单审核人员开放支付审核列表和审核接口。
- 灰度阶段 2：观察一个工作日后扩大到全部审核角色。
- 灰度退出条件：若监控指标或告警显示状态流转异常，立即停止灰度并执行应用回滚。

## 4. 上线检查项

- 核对审核值班人员、回滚负责人和发布时间窗已经确认。
- 核对监控面板、告警接收渠道和审核日志查询能力已可用。
- 核对预发环境审核通过、审核驳回和重复审核拦截已完成演练。
