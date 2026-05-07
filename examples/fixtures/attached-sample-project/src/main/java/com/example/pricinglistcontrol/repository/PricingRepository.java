package com.example.pricinglistcontrol.repository;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class PricingRepository {
    private final List<Map<String, Object>> pricingPlans = new ArrayList<>();

    public PricingRepository() {
        pricingPlans.add(plan("PR-001", "LINE-A", "WAIT_REVIEW", "COUNT_PACKAGE"));
        pricingPlans.add(plan("PR-002", "LINE-B", "ENABLED", "AMOUNT_PACKAGE"));
        pricingPlans.add(plan("PR-003", "LINE-A", "DRAFT", "COUNT_PACKAGE"));
    }

    public List<Map<String, Object>> query(String productLine, String status, String type) {
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> plan : pricingPlans) {
            if (productLine != null && !productLine.equals(plan.get("productLine"))) {
                continue;
            }
            if (status != null && !status.equals(plan.get("status"))) {
                continue;
            }
            if (type != null && !type.equals(plan.get("type"))) {
                continue;
            }
            result.add(new HashMap<>(plan));
        }
        return result;
    }

    public Map<String, Object> findById(String pricingId) {
        for (Map<String, Object> plan : pricingPlans) {
            if (pricingId.equals(plan.get("pricingId"))) {
                return plan;
            }
        }
        return null;
    }

    public Map<String, Object> save(Map<String, Object> plan) {
        Map<String, Object> existing = findById(String.valueOf(plan.get("pricingId")));
        if (existing != null) {
            existing.putAll(plan);
            return existing;
        }
        pricingPlans.add(new HashMap<>(plan));
        return plan;
    }

    private Map<String, Object> plan(String pricingId, String productLine, String status, String type) {
        Map<String, Object> item = new HashMap<>();
        item.put("pricingId", pricingId);
        item.put("productLine", productLine);
        item.put("status", status);
        item.put("type", type);
        return item;
    }
}
