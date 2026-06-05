#!/usr/bin/env node
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const node_fs_1 = __importDefault(require("node:fs"));
const scanner_1 = require("./scanner");
const TOOLS = [
    {
        name: "scan_modules",
        description: "Scan source files and return language-neutral module/class entities.",
        inputSchema: {
            type: "object",
            properties: {
                keywords: { type: "array", items: { type: "string" } },
                limit: { type: "number" },
                language: { type: "string" },
                scanRoots: { type: "array", items: { type: "string" } },
                forceRefresh: { type: "boolean" },
            },
        },
    },
    {
        name: "verify_class_exists",
        description: "Verify whether named classes/entities exist in the scanned source map.",
        inputSchema: {
            type: "object",
            properties: {
                class_names: { type: "array", items: { type: "string" } },
                language: { type: "string" },
                scanRoots: { type: "array", items: { type: "string" } },
            },
            required: ["class_names"],
        },
    },
    {
        name: "get_class_detail",
        description: "Return one scanned class/entity detail by simple or fully-qualified name.",
        inputSchema: {
            type: "object",
            properties: {
                class_name: { type: "string" },
                language: { type: "string" },
                scanRoots: { type: "array", items: { type: "string" } },
            },
            required: ["class_name"],
        },
    },
    {
        name: "refresh_module_map",
        description: "Scan sources and write module-map.json.",
        inputSchema: {
            type: "object",
            properties: {
                outputPath: { type: "string" },
                language: { type: "string" },
                scanRoots: { type: "array", items: { type: "string" } },
            },
        },
    },
];
function normalizeArgs(raw) {
    if (!raw || typeof raw !== "object") {
        return {};
    }
    const normalized = { ...raw };
    if (raw.force_refresh !== undefined && raw.forceRefresh === undefined) {
        normalized.forceRefresh = raw.force_refresh;
    }
    if (raw.scan_roots !== undefined && raw.scanRoots === undefined) {
        normalized.scanRoots = raw.scan_roots;
    }
    if (raw.output_path !== undefined && raw.outputPath === undefined) {
        normalized.outputPath = raw.output_path;
    }
    return normalized;
}
function callTool(name, rawArgs) {
    const args = normalizeArgs(rawArgs);
    if (name === "scan_modules") {
        return (0, scanner_1.scanModules)(args);
    }
    if (name === "verify_class_exists") {
        const classNames = Array.isArray(args.class_names) ? args.class_names.map(String) : [];
        return { results: (0, scanner_1.verifyClassExists)(classNames, args) };
    }
    if (name === "get_class_detail") {
        return { detail: (0, scanner_1.getClassDetail)(String(args.class_name || ""), args) };
    }
    if (name === "refresh_module_map") {
        return (0, scanner_1.writeModuleMap)(args);
    }
    throw new Error(`unknown tool: ${name}`);
}
function contentResult(payload) {
    return {
        content: [
            {
                type: "text",
                text: JSON.stringify(payload, null, 2),
            },
        ],
    };
}
function handleRequest(request) {
    if (request.method === "initialize") {
        return {
            jsonrpc: "2.0",
            id: request.id,
            result: {
                protocolVersion: "2024-11-05",
                capabilities: { tools: {} },
                serverInfo: { name: "project-explorer-mcp", version: "0.1.0" },
            },
        };
    }
    if (request.method === "tools/list") {
        return { jsonrpc: "2.0", id: request.id, result: { tools: TOOLS } };
    }
    if (request.method === "tools/call") {
        try {
            const name = String(request.params?.name || "");
            const args = request.params?.arguments || {};
            return { jsonrpc: "2.0", id: request.id, result: contentResult(callTool(name, args)) };
        }
        catch (error) {
            return { jsonrpc: "2.0", id: request.id, error: { code: -32000, message: error?.message || String(error) } };
        }
    }
    if (request.method === "notifications/initialized") {
        return null;
    }
    return {
        jsonrpc: "2.0",
        id: request.id,
        error: { code: -32601, message: `method not found: ${request.method}` },
    };
}
function parseCliArgs(argv) {
    const parsed = { args: {} };
    for (let index = 0; index < argv.length; index += 1) {
        const item = argv[index];
        if (item === "--tool") {
            parsed.tool = argv[index + 1];
            index += 1;
        }
        else if (item === "--arguments") {
            parsed.args = JSON.parse(argv[index + 1] || "{}");
            index += 1;
        }
    }
    return parsed;
}
async function runStdio() {
    const input = node_fs_1.default.readFileSync(0, "utf8");
    for (const line of input.split(/\r?\n/)) {
        if (!line.trim()) {
            continue;
        }
        const response = handleRequest(JSON.parse(line));
        if (response) {
            process.stdout.write(`${JSON.stringify(response)}\n`);
        }
    }
}
async function main() {
    const cli = parseCliArgs(process.argv.slice(2));
    if (cli.tool) {
        process.stdout.write(`${JSON.stringify(callTool(cli.tool, cli.args), null, 2)}\n`);
        return;
    }
    await runStdio();
}
main().catch((error) => {
    process.stderr.write(`${error?.stack || error}\n`);
    process.exit(1);
});
