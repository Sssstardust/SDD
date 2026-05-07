package com.example.pricinglistcontrol.ui;

import com.example.pricinglistcontrol.controller.PricingController;
import java.util.List;
import java.util.Map;

public class PricingUI {
    private final PricingController pricingController;

    public PricingUI(PricingController pricingController) {
        this.pricingController = pricingController;
    }

    public List<Map<String, Object>> showPricingList(String userId, Map<String, String> query) {
        return pricingController.getPricings(userId, query);
    }

    public Map<String, Object> submitReview(String pricingId, String reviewer) {
        return pricingController.review(pricingId, reviewer);
    }

    public Map<String, Object> submitUpdate(String pricingId, Map<String, Object> payload) {
        return pricingController.update(pricingId, payload);
    }
}
