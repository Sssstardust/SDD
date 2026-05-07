package com.example.pricinglistcontrol.service;

public class OrderUsageService {
    public boolean checkOrderRelation(String pricingId) {
        return "PR-002".equals(pricingId);
    }
}
