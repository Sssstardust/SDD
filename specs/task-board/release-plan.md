# Release Plan

```yaml
release:
  owner: task-board-ops
  approver: task-board-lead
  window: "2026-05-07 22:00-23:00 Asia/Shanghai"
  rollback:
    ready: true
    trigger: "error_rate_gt_1_percent_or_concurrency_conflict_spike"
    sql_down_confirmed: true
    app_switch: "task_board_write_enabled"
  monitoring:
    ready: true
    metrics:
      - task_board_api_success_rate
      - task_board_drag_sort_latency_p95
      - task_board_async_notification_lag
      - task_board_optimistic_lock_conflict_rate
  alerting:
    ready: true
    rules:
      - task_board_api_error_rate_high
      - task_board_async_consumer_delay_high
      - task_board_concurrency_conflict_rate_high
  rollout:
    ready: true
    batches:
      - "5% internal whitelist"
      - "30% project teams"
      - "100% all users"
```

## 1. 上线窗口

- 时间：2026-05-07 22:00-23:00（Asia/Shanghai）
- 负责人：task-board-ops
- 审批人：task-board-lead

## 2. 回滚方案

- 触发条件：接口错误率超过 1%，或乐观锁冲突率明显升高
- 回滚步骤：关闭 `task_board_write_enabled` 开关，停止异步通知消费，执行 `design-pack/数据库变更.sql` 中的 `DOWN` 块
- SQL DOWN / ROLLBACK 脚本：已在 `design-pack/数据库变更.sql` 中确认
- 应用开关：`task_board_write_enabled`

## 3. 监控与告警

- 核心指标：任务看板接口成功率、拖拽排序 P95、通知消费延迟、并发冲突率
- 告警规则：接口错误率高、异步消费积压高、并发冲突率高
- 观察窗口：首批灰度后观察 30 分钟，再决定是否扩大批次

## 4. 灰度策略

- 批次：先 5% 内部白名单，再 30% 项目组，最后全量
- 扩大条件：关键指标稳定，告警无新增
- 停止条件：出现高优先级告警或并发冲突率异常上升
