# Release Plan

```yaml
release:
  owner:
  approver:
  window:
  rollback:
    ready: false
    trigger:
    sql_down_confirmed: false
    app_switch:
  monitoring:
    ready: false
    metrics:
      - 
  alerting:
    ready: false
    rules:
      - 
  rollout:
    ready: false
    batches:
      - "5%"
      - "50%"
      - "100%"
```

## 1. 上线窗口

- 时间：
- 负责人：
- 审批人：

## 2. 回滚方案

- 触发条件：
- 回滚步骤：
- SQL DOWN / ROLLBACK 脚本：
- 应用开关：

## 3. 监控与告警

- 核心指标：
- 告警规则：
- 观察窗口：

## 4. 灰度策略

- 批次：
- 扩大条件：
- 停止条件：
