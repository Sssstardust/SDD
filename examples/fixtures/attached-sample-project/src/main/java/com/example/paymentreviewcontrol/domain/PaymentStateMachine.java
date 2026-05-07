package com.example.paymentreviewcontrol.domain;

public class PaymentStateMachine {
    public String transit(String currentStatus, String targetStatus) {
        if (!"WAIT_REVIEW".equals(currentStatus)) {
            throw new IllegalStateException("payment status is not reviewable");
        }
        if (!"APPROVED".equals(targetStatus) && !"REJECTED".equals(targetStatus)) {
            throw new IllegalArgumentException("unsupported target status");
        }
        return targetStatus;
    }
}
