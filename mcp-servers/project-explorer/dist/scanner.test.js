#!/usr/bin/env node
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const node_assert_1 = __importDefault(require("node:assert"));
const node_fs_1 = __importDefault(require("node:fs"));
const node_os_1 = __importDefault(require("node:os"));
const node_path_1 = __importDefault(require("node:path"));
const scanner_1 = require("./scanner");
const tmp = node_fs_1.default.mkdtempSync(node_path_1.default.join(node_os_1.default.tmpdir(), "project-explorer-"));
const src = node_path_1.default.join(tmp, "src");
node_fs_1.default.mkdirSync(src, { recursive: true });
node_fs_1.default.writeFileSync(node_path_1.default.join(src, "service.py"), [
    "class PaymentService:",
    "    def approve(self):",
    "        return True",
    "",
    "def helper():",
    "    return None",
].join("\n"), "utf8");
node_fs_1.default.writeFileSync(node_path_1.default.join(src, "controller.ts"), [
    "export class PaymentController {",
    "  approvePayment() { return true; }",
    "}",
].join("\n"), "utf8");
const pythonMap = (0, scanner_1.scanModules)({ language: "python", scanRoots: [src] }, tmp);
(0, node_assert_1.default)(pythonMap.classes.some((item) => item.simple_name === "PaymentService"));
(0, node_assert_1.default)((0, scanner_1.verifyClassExists)(["PaymentService", "Missing"], { language: "python", scanRoots: [src] }, tmp).PaymentService);
(0, node_assert_1.default)(!(0, scanner_1.verifyClassExists)(["PaymentService", "Missing"], { language: "python", scanRoots: [src] }, tmp).Missing);
const tsMap = (0, scanner_1.scanModules)({ language: "typescript", scanRoots: [src] }, tmp);
(0, node_assert_1.default)(tsMap.classes.some((item) => item.simple_name === "PaymentController"));
(0, node_assert_1.default)((0, scanner_1.getClassDetail)("PaymentController", { language: "typescript", scanRoots: [src] }, tmp)?.methods.includes("approvePayment"));
console.log("scanner tests passed");
