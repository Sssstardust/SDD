#!/usr/bin/env node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const fs = require("node:fs");
const path = require("node:path");
const readline = require("node:readline");
const rule_map_1 = require("./rule-map");
const PACKAGE = JSON.parse(fs.readFileSync(path.resolve(__dirname, "..", "package.json"), "utf8"));
function parseArgs(argv) {
    const result = {};
    for (let index = 0; index < argv.length; index += 1) {
        const current = argv[index];
        if (!current.startsWith("--")) {
            continue;
        }
        const key = current.slice(2);
        const next = argv[index + 1];
        if (!next || next.startsWith("--")) {
            result[key] = true;
        }
        else {
            result[key] = next;
            index += 1;
        }
    }
    return result;
}
function parseArguments(text) {
    if (!text) {
        return {};
    }
    try {
        return JSON.parse(text);
    }
    catch {
        const normalized = text
            .replace(/\bTrue\b/g, "true")
            .replace(/\bFalse\b/g, "false")
            .replace(/\bNone\b/g, "null")
            .replace(/'/g, '"');
        return JSON.parse(normalized);
    }
}
function listRuleFiles() {
    if (!fs.existsSync(rule_map_1.STANDARDS_DIR)) {
        return [];
    }
    return fs
        .readdirSync(rule_map_1.STANDARDS_DIR, { withFileTypes: true })
        .filter((entry) => entry.isFile() && entry.name.endsWith(".md"))
        .map((entry) => ({
        file: entry.name,
        path: path.join(rule_map_1.STANDARDS_DIR, entry.name),
    }));
}
function toolDispatch(name, argumentsObject) {
    if (name === "list_rules") {
        return {
            count: (0, rule_map_1.listRules)().length,
            rules: (0, rule_map_1.listRules)(),
            files: listRuleFiles(),
        };
    }
    if (name === "get_rule") {
        const id = String(argumentsObject.rule_id ?? argumentsObject.file ?? "");
        return (0, rule_map_1.getRule)(id);
    }
    if (name === "get_constraints") {
        const ruleIds = Array.isArray(argumentsObject.rule_ids) ? argumentsObject.rule_ids : undefined;
        return (0, rule_map_1.getConstraints)(ruleIds);
    }
    if (name === "get_feature_rules") {
        const featureType = String(argumentsObject.feature_type ?? "general");
        const capabilityTags = Array.isArray(argumentsObject.capability_tags) ? argumentsObject.capability_tags.map((item) => String(item)) : [];
        const ruleFiles = Array.isArray(argumentsObject.rule_files) ? argumentsObject.rule_files.map((item) => String(item)) : undefined;
        const payload = (0, rule_map_1.getFeatureRules)(featureType, capabilityTags, ruleFiles);
        return {
            ...payload,
            rule_contents: payload.rules.reduce((acc, rule) => {
                acc[rule.file] = (0, rule_map_1.readRuleContent)(rule.file);
                return acc;
            }, {}),
        };
    }
    throw new Error(`未知工具: ${name}`);
}
function runCli(tool, argumentsText) {
    const payload = toolDispatch(tool, parseArguments(argumentsText));
    process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
}
function toolDefinitions() {
    return [
        {
            name: "list_rules",
            description: "列出可用架构规范及对应规则文件",
            inputSchema: {
                type: "object",
                properties: {},
            },
        },
        {
            name: "get_rule",
            description: "读取单条规范原文和元信息",
            inputSchema: {
                type: "object",
                properties: {
                    rule_id: { type: "string" },
                    file: { type: "string" },
                },
            },
        },
        {
            name: "get_constraints",
            description: "返回结构化约束集合，可按 rule_ids 过滤",
            inputSchema: {
                type: "object",
                properties: {
                    rule_ids: { type: "array", items: { type: "string" } },
                },
            },
        },
        {
            name: "get_feature_rules",
            description: "根据 feature_type 和 capability_tags 返回适用规范与结构化约束",
            inputSchema: {
                type: "object",
                properties: {
                    feature_type: { type: "string" },
                    capability_tags: { type: "array", items: { type: "string" } },
                    rule_files: { type: "array", items: { type: "string" } },
                },
                required: ["feature_type"],
            },
        },
    ];
}
function writeJsonRpc(id, result, isError = false) {
    const message = { jsonrpc: "2.0", id, result };
    if (isError) {
        delete message.result;
        message.error = result;
    }
    process.stdout.write(`${JSON.stringify(message)}\n`);
}
function runMcpStdio() {
    const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
    rl.on("line", (line) => {
        if (!line || !line.trim()) {
            return;
        }
        let message;
        try {
            message = JSON.parse(line);
        }
        catch {
            writeJsonRpc(null, { code: -32700, message: "Parse error" }, true);
            return;
        }
        const { id, method, params } = message;
        try {
            if (method === "initialize") {
                writeJsonRpc(id, {
                    protocolVersion: params && params.protocolVersion ? params.protocolVersion : "2024-11-05",
                    capabilities: { tools: {} },
                    serverInfo: {
                        name: PACKAGE.name,
                        version: PACKAGE.version,
                    },
                });
                return;
            }
            if (method === "notifications/initialized") {
                return;
            }
            if (method === "ping") {
                writeJsonRpc(id, {});
                return;
            }
            if (method === "tools/list") {
                writeJsonRpc(id, { tools: toolDefinitions() });
                return;
            }
            if (method === "tools/call") {
                const name = params && params.name;
                const argumentsObject = (params && params.arguments) || {};
                const payload = toolDispatch(name, argumentsObject);
                writeJsonRpc(id, {
                    content: [{ type: "text", text: JSON.stringify(payload, null, 2) }],
                    isError: false,
                });
                return;
            }
            writeJsonRpc(id, { code: -32601, message: `Method not found: ${String(method)}` }, true);
        }
        catch (error) {
            const messageText = error instanceof Error ? error.message : String(error);
            writeJsonRpc(id, { code: -32000, message: messageText }, true);
        }
    });
}
function main() {
    const args = parseArgs(process.argv.slice(2));
    if (args.tool) {
        runCli(String(args.tool), typeof args.arguments === "string" ? args.arguments : "{}");
        return;
    }
    runMcpStdio();
}
main();
