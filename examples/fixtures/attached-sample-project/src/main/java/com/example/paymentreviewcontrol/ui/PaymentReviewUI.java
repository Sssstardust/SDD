package com.example.paymentreviewcontrol.ui;

import com.example.paymentreviewcontrol.controller.PaymentReviewController;
import java.util.List;
import java.util.Map;

public class PaymentReviewUI {
    private final PaymentReviewController paymentReviewController;

    public PaymentReviewUI(PaymentReviewController paymentReviewController) {
        this.paymentReviewController = paymentReviewController;
    }

    public List<Map<String, Object>> showPendingPayments(String reviewer) {
        return paymentReviewController.listPending(reviewer);
    }

    public Map<String, Object> approvePayment(String paymentId, String reviewer) {
        return paymentReviewController.approve(paymentId, reviewer);
    }

    public Map<String, Object> rejectPayment(String paymentId, String reviewer, String reason) {
        return paymentReviewController.reject(paymentId, reviewer, reason);
    }
}
