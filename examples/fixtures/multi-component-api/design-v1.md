# Multi Component API Design

```mermaid
sequenceDiagram
    participant P as PaymentController
    participant S as PaymentSyncService
    P->>S: syncOrderStatus()
```
