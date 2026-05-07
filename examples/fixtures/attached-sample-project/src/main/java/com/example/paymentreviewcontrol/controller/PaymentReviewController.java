package com.example.paymentreviewcontrol.controller;

import com.example.paymentreviewcontrol.service.PaymentReviewService;
import java.util.List;
import java.util.Map;

public class PaymentReviewController {
    private final PaymentReviewService paymentReviewService;

    public PaymentReviewController(PaymentReviewService paymentReviewService) {
        this.paymentReviewService = paymentReviewService;
    }

    public List<Map<String, Object>> listPending(String reviewer) {
        return paymentReviewService.listPendingPayments(reviewer);
    }

    public Map<String, Object> approve(String paymentId, String reviewer) {
        return paymentReviewService.approve(paymentId, reviewer);
    }

    public Map<String, Object> reject(String paymentId, String reviewer, String reason) {
        return paymentReviewService.reject(paymentId, reviewer, reason);
    }
}
