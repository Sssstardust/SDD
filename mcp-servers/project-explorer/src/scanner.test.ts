#!/usr/bin/env node

import assert from "node:assert";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { getClassDetail, scanModules, verifyClassExists } from "./scanner";

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "project-explorer-"));
const src = path.join(tmp, "src");
fs.mkdirSync(src, { recursive: true });
fs.writeFileSync(
  path.join(src, "service.py"),
  [
    "class PaymentService:",
    "    def approve(self):",
    "        return True",
    "",
    "def helper():",
    "    return None",
  ].join("\n"),
  "utf8",
);
fs.writeFileSync(
  path.join(src, "controller.ts"),
  [
    "export class PaymentController {",
    "  approvePayment() { return true; }",
    "}",
  ].join("\n"),
  "utf8",
);

const pythonMap = scanModules({ language: "python", scanRoots: [src] }, tmp);
assert(pythonMap.classes.some((item) => item.simple_name === "PaymentService"));
assert(verifyClassExists(["PaymentService", "Missing"], { language: "python", scanRoots: [src] }, tmp).PaymentService);
assert(!verifyClassExists(["PaymentService", "Missing"], { language: "python", scanRoots: [src] }, tmp).Missing);

const tsMap = scanModules({ language: "typescript", scanRoots: [src] }, tmp);
assert(tsMap.classes.some((item) => item.simple_name === "PaymentController"));
assert(getClassDetail("PaymentController", { language: "typescript", scanRoots: [src] }, tmp)?.methods.includes("approvePayment"));

console.log("scanner tests passed");
