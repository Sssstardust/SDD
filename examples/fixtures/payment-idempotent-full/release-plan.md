# Release Plan

```yaml
release:
  owner: payment-owner
  approver: payment-approver
  rollback:
    ready: true
  monitoring:
    ready: true
    metrics:
      - payment_review_approve_success_rate
      - payment_review_duplicate_conflict_rate
  alerting:
    ready: true
    rules:
      - payment_review_duplicate_conflict_spike
      - payment_review_state_inconsistent
  rollout:
    ready: true
    batches:
      - name: canary
        scope: 10%
      - name: full
        scope: 100%
```
