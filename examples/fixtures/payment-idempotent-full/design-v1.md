# Payment Idempotent Full Design

```mermaid
sequenceDiagram
    participant C as PaymentReviewController
    participant S as PaymentReviewService
    C->>S: approvePayment()
```
