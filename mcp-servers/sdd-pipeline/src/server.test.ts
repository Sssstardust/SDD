#!/usr/bin/env node

import assert from "node:assert/strict";

import { implementationSummaryFromReport, shouldRunAsyncByDefault, toolDispatch, wantsAsync } from "./server";

const DEFAULT_ASYNC_TOOLS = [
  "generate_feature_brief",
  "refresh_baseline",
  "prepare_design_cycle",
  "design_cycle",
  "project_console_cycle",
  "project_cycle",
  "continue_project_flow",
  "validate_all_reports",
  "design_gates",
  "implementation_gates",
  "approved_implementation_cycle",
  "gate5",
  "release_gate",
  "onboard_project",
  "install_runtime",
  "feature_repair",
  "full_flow",
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
assert.equal(shouldRunAsyncByDefault("approve_design"), false);
assert.equal(shouldRunAsyncByDefault("init_feature"), false);
assert.equal(shouldRunAsyncByDefault("feature_doctor"), false);

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

const health = toolDispatch("health_check", {});
assert.equal(typeof health.status, "string");
assert.equal("interface_path" in health, true);

const toolList = toolDispatch("list_pipeline_commands", {});
assert.equal(Array.isArray(toolList.tools), true);
for (const toolName of [
  "list_attachment_profiles",
  "set_active_attachment_profile",
  "install_runtime",
  "feature_doctor",
  "feature_repair",
  "init_feature",
  "generate_feature_brief",
  "approve_design",
  "prepare_design_cycle",
  "design_cycle",
  "implementation_gates",
  "approved_implementation_cycle",
  "continue_project_flow",
  "project_cycle",
  "full_flow",
]) {
  assert.equal(toolList.tools.some((tool: { name: string }) => tool.name === toolName), true, `${toolName} should be listed`);
}

process.stdout.write("sdd-pipeline server tests passed\n");
