# Release Plan

```yaml
release:
  owner: db-owner
  approver: db-approver
  rollback:
    ready: true
  monitoring:
    ready: true
    metrics:
      - pricing_item_create_success
  alerting:
    ready: true
    rules:
      - pricing_item_error_rate
  rollout:
    ready: true
    batches:
      - name: canary
        scope: 20%
      - name: full
        scope: 100%
```
