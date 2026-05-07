package com.example.pricinglistcontrol.controller;

import com.example.pricinglistcontrol.service.PricingPermissionService;
import com.example.pricinglistcontrol.service.PricingService;
import java.util.List;
import java.util.Map;

public class PricingController {
    private final PricingPermissionService pricingPermissionService;
    private final PricingService pricingService;

    public PricingController(PricingPermissionService pricingPermissionService, PricingService pricingService) {
        this.pricingPermissionService = pricingPermissionService;
        this.pricingService = pricingService;
    }

    public List<Map<String, Object>> getPricings(String userId, Map<String, String> query) {
        List<String> visibleProductLines = pricingPermissionService.filterVisibleProductLines(userId);
        return pricingService.listPricings(query, visibleProductLines);
    }

    public Map<String, Object> review(String pricingId, String reviewer) {
        return pricingService.reviewPricing(pricingId, reviewer);
    }

    public Map<String, Object> update(String pricingId, Map<String, Object> payload) {
        return pricingService.updatePricing(pricingId, payload);
    }
}
