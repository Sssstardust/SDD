#!/usr/bin/env node

import assert from "node:assert/strict";

import { shouldRunAsyncByDefault, wantsAsync } from "./server";

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

process.stdout.write("sdd-pipeline server tests passed\n");
