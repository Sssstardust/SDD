#!/usr/bin/env node

import assert from "node:assert/strict";

import { implementationSummaryFromReport, shouldRunAsyncByDefault, wantsAsync } from "./server";

const DEFAULT_ASYNC_TOOLS = [
  "refresh_baseline",
  "project_console_cycle",
  "validate_all_reports",
  "design_gates",
  "gate5",
  "release_gate",
  "onboard_project",
];

for (const toolName of DEFAULT_ASYNC_TOOLS) {
  assert.equal(
    shouldRunAsyncByDefault(toolName),
    true,
    `${toolName} should run asynchronously by default`,
  );
}

assert.equal(shouldRunAsyncByDefault("project_next"), false);
assert.equal(shouldRunAsyncByDefault("flow_status"), false);
assert.equal(shouldRunAsyncByDefault("validate_reports"), false);
assert.equal(shouldRunAsyncByDefault("generate_task_slices"), false);

assert.equal(wantsAsync({}, true), true);
assert.equal(wantsAsync({}, false), false);
assert.equal(wantsAsync({ async: true }, false), true);
assert.equal(wantsAsync({ async: false }, true), false);

assert.deepEqual(
  implementationSummaryFromReport({
    implementation_result: "WARN",
    implementation_method_framework_evidence: {
      inherited_matches: 1,
      mybatis_bound_matches: 2,
    },
    implementation_method_match_highlights: [{ class_name: "OrderMapper" }],
    gate5_admission_summary: {
      result: "WARN",
      warning_admissions: ["real_test_req"],
    },
  }),
  {
    implementation_result: "WARN",
    implementation_framework_evidence: {
      inherited_matches: 1,
      mybatis_bound_matches: 2,
    },
    implementation_match_highlights: [{ class_name: "OrderMapper" }],
    gate5_admission_summary: {
      result: "WARN",
      warning_admissions: ["real_test_req"],
    },
  },
);

assert.deepEqual(implementationSummaryFromReport(null), {
  implementation_result: null,
  implementation_framework_evidence: {},
  implementation_match_highlights: [],
});

assert.equal(
  typeof {
    gate3_ai_review: {
      result: "WARN",
      mode: "rule-modeled-review",
    },
  }.gate3_ai_review.result,
  "string",
);

assert.equal(
  typeof {
    candidate: {
      gate3_ai_review: {
        result: "WARN",
      },
    },
  }.candidate.gate3_ai_review.result,
  "string",
);

assert.equal(
  typeof {
    gate_summary: {
      gate3_ai: {
        WARN: 1,
      },
    },
  }.gate_summary.gate3_ai.WARN,
  "number",
);

assert.equal(
  typeof {
    project_highlights: {
      gate5_fail_count: 1,
    },
  }.project_highlights.gate5_fail_count,
  "number",
);

assert.equal(
  "strict_recommended" in {
    strict_recommended: true,
    strict_next_step: true,
  },
  true,
);

process.stdout.write("sdd-pipeline server tests passed\n");
