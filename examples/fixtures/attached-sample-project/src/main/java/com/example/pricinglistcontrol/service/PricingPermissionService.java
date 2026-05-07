package com.example.pricinglistcontrol.service;

import java.util.ArrayList;
import java.util.List;

public class PricingPermissionService {
    public List<String> filterVisibleProductLines(String userId) {
        List<String> lines = new ArrayList<>();
        if (userId == null || userId.isBlank()) {
            return lines;
        }
        lines.add("LINE-A");
        if (userId.startsWith("auditor")) {
            lines.add("LINE-B");
        }
        return lines;
    }
}
