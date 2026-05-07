package com.example.paymentreviewcontrol.repository;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class PaymentOrderRepository {
    private final Map<String, Map<String, Object>> paymentOrders = new HashMap<>();

    public PaymentOrderRepository() {
        paymentOrders.put("PAY-001", order("PAY-001", "WAIT_REVIEW"));
        paymentOrders.put("PAY-002", order("PAY-002", "APPROVED"));
    }

    public List<Map<String, Object>> findByStatus(String status) {
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> order : paymentOrders.values()) {
            if (status.equals(order.get("status"))) {
                result.add(new HashMap<>(order));
            }
        }
        return result;
    }

    public Map<String, Object> findById(String paymentId) {
        return paymentOrders.get(paymentId);
    }

    public Map<String, Object> save(Map<String, Object> order) {
        paymentOrders.put(String.valueOf(order.get("paymentId")), new HashMap<>(order));
        return order;
    }

    private Map<String, Object> order(String paymentId, String status) {
        Map<String, Object> order = new HashMap<>();
        order.put("paymentId", paymentId);
        order.put("status", status);
        return order;
    }
}
