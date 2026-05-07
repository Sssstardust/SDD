package com.example.paymentreviewcontrol.service;

import com.example.paymentreviewcontrol.domain.PaymentStateMachine;
import com.example.paymentreviewcontrol.repository.PaymentOrderRepository;
import com.example.paymentreviewcontrol.repository.PaymentReviewRecordRepository;
import java.util.List;
import java.util.Map;

public class PaymentReviewService {
    private final PaymentOrderRepository paymentOrderRepository;
    private final PaymentReviewRecordRepository paymentReviewRecordRepository;
    private final PaymentStateMachine paymentStateMachine;

    public PaymentReviewService(
        PaymentOrderRepository paymentOrderRepository,
        PaymentReviewRecordRepository paymentReviewRecordRepository,
        PaymentStateMachine paymentStateMachine
    ) {
        this.paymentOrderRepository = paymentOrderRepository;
        this.paymentReviewRecordRepository = paymentReviewRecordRepository;
        this.paymentStateMachine = paymentStateMachine;
    }

    public List<Map<String, Object>> listPendingPayments(String reviewer) {
        if (reviewer == null || reviewer.isBlank()) {
            throw new IllegalArgumentException("reviewer required");
        }
        return paymentOrderRepository.findByStatus("WAIT_REVIEW");
    }

    public Map<String, Object> approve(String paymentId, String reviewer) {
        Map<String, Object> payment = requireReviewablePayment(paymentId);
        payment.put("status", paymentStateMachine.transit(String.valueOf(payment.get("status")), "APPROVED"));
        payment.put("reviewer", reviewer);
        paymentReviewRecordRepository.appendRecord(paymentId, reviewer, "APPROVED", "");
        return paymentOrderRepository.save(payment);
    }

    public Map<String, Object> reject(String paymentId, String reviewer, String reason) {
        if (reason == null || reason.isBlank()) {
            throw new IllegalArgumentException("reject reason required");
        }
        Map<String, Object> payment = requireReviewablePayment(paymentId);
        payment.put("status", paymentStateMachine.transit(String.valueOf(payment.get("status")), "REJECTED"));
        payment.put("reviewer", reviewer);
        payment.put("rejectReason", reason);
        paymentReviewRecordRepository.appendRecord(paymentId, reviewer, "REJECTED", reason);
        return paymentOrderRepository.save(payment);
    }

    private Map<String, Object> requireReviewablePayment(String paymentId) {
        Map<String, Object> payment = paymentOrderRepository.findById(paymentId);
        if (payment == null) {
            throw new IllegalArgumentException("payment not found");
        }
        if (!"WAIT_REVIEW".equals(payment.get("status"))) {
            throw new IllegalStateException("payment already reviewed");
        }
        return payment;
    }
}
