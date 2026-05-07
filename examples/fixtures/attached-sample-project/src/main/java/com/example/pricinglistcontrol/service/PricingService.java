package com.example.pricinglistcontrol.service;

import com.example.pricinglistcontrol.repository.PricingRepository;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class PricingService {
    private final PricingRepository pricingRepository;
    private final OrderUsageService orderUsageService;

    public PricingService(PricingRepository pricingRepository, OrderUsageService orderUsageService) {
        this.pricingRepository = pricingRepository;
        this.orderUsageService = orderUsageService;
    }

    public List<Map<String, Object>> listPricings(Map<String, String> query, List<String> visibleProductLines) {
        List<Map<String, Object>> filtered = new ArrayList<>();
        String status = query == null ? null : query.get("status");
        String type = query == null ? null : query.get("type");
        for (String line : visibleProductLines) {
            filtered.addAll(pricingRepository.query(line, status, type));
        }
        return filtered;
    }

    public Map<String, Object> reviewPricing(String pricingId, String reviewer) {
        Map<String, Object> pricing = pricingRepository.findById(pricingId);
        if (pricing == null) {
            throw new IllegalArgumentException("pricing not found");
        }
        pricing.put("status", "ENABLED");
        pricing.put("reviewer", reviewer);
        return pricingRepository.save(pricing);
    }

    public Map<String, Object> updatePricing(String pricingId, Map<String, Object> payload) {
        Map<String, Object> pricing = pricingRepository.findById(pricingId);
        if (pricing == null) {
            throw new IllegalArgumentException("pricing not found");
        }
        boolean linked = orderUsageService.checkOrderRelation(pricingId);
        if (linked && !"COUNT_PACKAGE".equals(pricing.get("type")) && !"AMOUNT_PACKAGE".equals(pricing.get("type"))) {
            throw new IllegalStateException("pricing linked by order");
        }

        Map<String, Object> updated = new HashMap<>(pricing);
        if (payload != null) {
            updated.putAll(payload);
        }
        return pricingRepository.save(updated);
    }
}
