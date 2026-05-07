# Release Plan

```yaml
release:
  owner: component-owner
  approver: component-approver
  rollback:
    ready: true
  monitoring:
    ready: true
    metrics:
      - payment_order_sync_success
  alerting:
    ready: true
    rules:
      - payment_order_sync_error
  rollout:
    ready: true
    batches:
      - name: canary
        scope: payment-service only
      - name: full
        scope: payment-service and order-service
```
