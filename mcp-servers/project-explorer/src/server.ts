#!/usr/bin/env node

import * as fs from "node:fs";
import * as path from "node:path";
import * as readline from "node:readline";
import {
  dumpModuleMapPayload,
  getClassDetail,
  listMethods,
  scanModules,
  verifyClassExists,
} from "./lib/scanner";

type JsonRecord = Record<string, any>;

const PACKAGE = JSON.parse(
  fs.readFileSync(path.resolve(__dirname, "..", "package.json"), "utf8")
) as { name: string; version: string };

function parseArgs(argv: string[]): Record<string, string | boolean> {
  const result: Record<string, string | boolean> = {};
  for (let index = 0; index < argv.length; index += 1) {
    const current = argv[index];
    if (!current.startsWith("--")) {
      continue;
    }
    const key = current.slice(2);
    const next = argv[index + 1];
    if (!next || next.startsWith("--")) {
      result[key] = true;
    } else {
      result[key] = next;
      index += 1;
    }
  }
  return result;
}

function parseArguments(text?: string): JsonRecord {
  if (!text) {
    return {};
  }
  try {
    return JSON.parse(text) as JsonRecord;
  } catch {
    const normalized = text
      .replace(/\bTrue\b/g, "true")
      .replace(/\bFalse\b/g, "false")
      .replace(/\bNone\b/g, "null")
      .replace(/'/g, '"');
    return JSON.parse(normalized) as JsonRecord;
  }
}

function toolDispatch(name: string, argumentsObject: JsonRecord): JsonRecord {
  if (name === "health_check") {
    return {
      status: "ok",
      reason: "project-explorer scanner entrypoints are available",
    };
  }
  if (name === "scan_modules") {
    return scanModules({
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
    return verifyClassExists({
      classNames,
      forceRefresh: Boolean(argumentsObject.force_refresh ?? argumentsObject.forceRefresh),
    });
  }
  if (name === "list_methods") {
    return listMethods({
      className: argumentsObject.class_name ?? argumentsObject.className ?? null,
      fqn: argumentsObject.fqn ?? null,
      forceRefresh: Boolean(argumentsObject.force_refresh ?? argumentsObject.forceRefresh),
    });
  }
  if (name === "get_class_detail") {
    return getClassDetail({
      className: argumentsObject.class_name ?? argumentsObject.className ?? null,
      fqn: argumentsObject.fqn ?? null,
      forceRefresh: Boolean(argumentsObject.force_refresh ?? argumentsObject.forceRefresh),
    });
  }
  if (name === "dump_module_map") {
    return dumpModuleMapPayload({
      forceRefresh: Boolean(argumentsObject.force_refresh ?? argumentsObject.forceRefresh),
      scanRoots: argumentsObject.scan_roots ?? argumentsObject.scanRoots,
      designRoots: argumentsObject.design_roots ?? argumentsObject.designRoots,
    });
  }
  throw new Error(`未知工具: ${name}`);
}

function runCli(tool: string, argumentsText?: string): void {
  const argumentsObject = parseArguments(argumentsText);
  const payload = toolDispatch(tool, argumentsObject);
  process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
}

function toolDefinitions(): JsonRecord[] {
  return [
    {
      name: "health_check",
      description: "返回 MCP Server 健康状态",
      inputSchema: {
        type: "object",
        properties: {},
      },
    },
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

function writeJsonRpc(id: unknown, result: JsonRecord, isError = false): void {
  const message: JsonRecord = {
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

function runMcpStdio(): void {
  const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
  rl.on("line", (line) => {
    if (!line || !line.trim()) {
      return;
    }

    let message: JsonRecord;
    try {
      message = JSON.parse(line) as JsonRecord;
    } catch {
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
    } catch (error) {
      const messageText = error instanceof Error ? error.message : String(error);
      writeJsonRpc(id, { code: -32000, message: messageText }, true);
    }
  });
}

function main(): void {
  const args = parseArgs(process.argv.slice(2));
  if (args.tool) {
    runCli(String(args.tool), typeof args.arguments === "string" ? args.arguments : "{}");
    return;
  }
  runMcpStdio();
}

main();
