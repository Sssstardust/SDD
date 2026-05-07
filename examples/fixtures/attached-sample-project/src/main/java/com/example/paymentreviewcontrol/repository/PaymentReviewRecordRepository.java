package com.example.paymentreviewcontrol.repository;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class PaymentReviewRecordRepository {
    private final List<Map<String, Object>> records = new ArrayList<>();

    public void appendRecord(String paymentId, String reviewer, String result, String reason) {
        Map<String, Object> record = new HashMap<>();
        record.put("paymentId", paymentId);
        record.put("reviewer", reviewer);
        record.put("result", result);
        record.put("reason", reason);
        records.add(record);
    }

    public List<Map<String, Object>> listRecords() {
        return new ArrayList<>(records);
    }
}
