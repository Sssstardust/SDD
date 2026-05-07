#!/usr/bin/env node
"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
const fs = __importStar(require("node:fs"));
const path = __importStar(require("node:path"));
const readline = __importStar(require("node:readline"));
const scanner_1 = require("./lib/scanner");
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
function toolDispatch(name, argumentsObject) {
    if (name === "scan_modules") {
        return (0, scanner_1.scanModules)({
            keywords: argumentsObject.keywords,
            forceRefresh: Boolean(argumentsObject.force_refresh ?? argumentsObject.forceRefresh),
            limit: argumentsObject.limit == null ? 20 : Number(argumentsObject.limit),
            scanRoots: argumentsObject.scan_roots ?? argumentsObject.scanRoots,
            designRoots: argumentsObject.design_roots ?? argumentsObject.designRoots,
        });
    }
    if (name === "verify_class_exists") {
        const classNames = Array.isArray(argumentsObject.class_names)
            ? argumentsObject.class_names
            : Array.isArray(argumentsObject.classNames)
                ? argumentsObject.classNames
                : argumentsObject.class_name
                    ? [argumentsObject.class_name]
                    : argumentsObject.className
                        ? [argumentsObject.className]
                        : [];
        return (0, scanner_1.verifyClassExists)({
            classNames,
            forceRefresh: Boolean(argumentsObject.force_refresh ?? argumentsObject.forceRefresh),
        });
    }
    if (name === "list_methods") {
        return (0, scanner_1.listMethods)({
            className: argumentsObject.class_name ?? argumentsObject.className ?? null,
            fqn: argumentsObject.fqn ?? null,
            forceRefresh: Boolean(argumentsObject.force_refresh ?? argumentsObject.forceRefresh),
        });
    }
    if (name === "get_class_detail") {
        return (0, scanner_1.getClassDetail)({
            className: argumentsObject.class_name ?? argumentsObject.className ?? null,
            fqn: argumentsObject.fqn ?? null,
            forceRefresh: Boolean(argumentsObject.force_refresh ?? argumentsObject.forceRefresh),
        });
    }
    if (name === "dump_module_map") {
        return (0, scanner_1.dumpModuleMapPayload)({
            forceRefresh: Boolean(argumentsObject.force_refresh ?? argumentsObject.forceRefresh),
            scanRoots: argumentsObject.scan_roots ?? argumentsObject.scanRoots,
            designRoots: argumentsObject.design_roots ?? argumentsObject.designRoots,
        });
    }
    throw new Error(`未知工具: ${name}`);
}
function runCli(tool, argumentsText) {
    const argumentsObject = parseArguments(argumentsText);
    const payload = toolDispatch(tool, argumentsObject);
    process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
}
function toolDefinitions() {
    return [
        {
            name: "scan_modules",
            description: "根据关键词扫描相关类、包、模块、类型、来源文件和公开方法",
            inputSchema: {
                type: "object",
                properties: {
                    keywords: { type: "array", items: { type: "string" } },
                    force_refresh: { type: "boolean" },
                    limit: { type: "integer" },
                    scan_roots: { type: "array", items: { type: "string" } },
                    design_roots: { type: "array", items: { type: "string" } },
                },
            },
        },
        {
            name: "verify_class_exists",
            description: "校验指定类名或 FQN 是否存在",
            inputSchema: {
                type: "object",
                properties: {
                    class_names: { type: "array", items: { type: "string" } },
                    force_refresh: { type: "boolean" },
                },
                required: ["class_names"],
            },
        },
        {
            name: "list_methods",
            description: "返回指定类的公开方法签名",
            inputSchema: {
                type: "object",
                properties: {
                    class_name: { type: "string" },
                    fqn: { type: "string" },
                    force_refresh: { type: "boolean" },
                },
            },
        },
        {
            name: "get_class_detail",
            description: "返回类的包名、文件、方法、模块和简单依赖",
            inputSchema: {
                type: "object",
                properties: {
                    class_name: { type: "string" },
                    fqn: { type: "string" },
                    force_refresh: { type: "boolean" },
                },
            },
        },
    ];
}
function writeJsonRpc(id, result, isError = false) {
    const message = {
        jsonrpc: "2.0",
        id,
        result,
    };
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
