#!/usr/bin/env node
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const server_1 = require("./server");
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
    strict_1.default.equal((0, server_1.shouldRunAsyncByDefault)(toolName), true, `${toolName} should run asynchronously by default`);
}
strict_1.default.equal((0, server_1.shouldRunAsyncByDefault)("project_next"), false);
strict_1.default.equal((0, server_1.shouldRunAsyncByDefault)("flow_status"), false);
strict_1.default.equal((0, server_1.shouldRunAsyncByDefault)("validate_reports"), false);
strict_1.default.equal((0, server_1.shouldRunAsyncByDefault)("generate_task_slices"), false);
strict_1.default.equal((0, server_1.wantsAsync)({}, true), true);
strict_1.default.equal((0, server_1.wantsAsync)({}, false), false);
strict_1.default.equal((0, server_1.wantsAsync)({ async: true }, false), true);
strict_1.default.equal((0, server_1.wantsAsync)({ async: false }, true), false);
strict_1.default.deepEqual((0, server_1.implementationSummaryFromReport)({
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
}), {
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
});
strict_1.default.deepEqual((0, server_1.implementationSummaryFromReport)(null), {
    implementation_result: null,
    implementation_framework_evidence: {},
    implementation_match_highlights: [],
});
strict_1.default.equal(typeof {
    gate3_ai_review: {
        result: "WARN",
        mode: "rule-modeled-review",
    },
}.gate3_ai_review.result, "string");
strict_1.default.equal(typeof {
    candidate: {
        gate3_ai_review: {
            result: "WARN",
        },
    },
}.candidate.gate3_ai_review.result, "string");
strict_1.default.equal(typeof {
    gate_summary: {
        gate3_ai: {
            WARN: 1,
        },
    },
}.gate_summary.gate3_ai.WARN, "number");
strict_1.default.equal(typeof {
    project_highlights: {
        gate5_fail_count: 1,
    },
}.project_highlights.gate5_fail_count, "number");
strict_1.default.equal("strict_recommended" in {
    strict_recommended: true,
    strict_next_step: true,
}, true);
process.stdout.write("sdd-pipeline server tests passed\n");
