# Feature Brief

```yaml
project_mode: brownfield
feature_name: payment-idempotent-full
sdd_level: full
risk_tier: high
capability_tags:
  - api
  - payment
  - idempotent
requirements:
  - req_id: REQ-001
    priority: P0
    title: approve payment exactly once
    description: payment approval should remain idempotent and avoid duplicate state changes
```
