#!/usr/bin/env node

import * as fs from "node:fs";
import * as path from "node:path";
import * as readline from "node:readline";
import {
  getConstraints,
  getFeatureRules,
  getLayeringSemantics,
  getRule,
  listRules,
  readRuleContent,
  STANDARDS_DIR,
} from "./rule-map";

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

function listRuleFiles(): JsonRecord[] {
  if (!fs.existsSync(STANDARDS_DIR)) {
    return [];
  }
  return fs
    .readdirSync(STANDARDS_DIR, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith(".md"))
    .map((entry) => ({
      file: entry.name,
      path: path.join(STANDARDS_DIR, entry.name),
    }));
}

function toolDispatch(name: string, argumentsObject: JsonRecord): JsonRecord {
  if (name === "health_check") {
    return {
      status: "ok",
      reason: "arch-standard rules are readable from docs/arch-standards",
    };
  }
  if (name === "list_rules") {
    return {
      count: listRules().length,
      rules: listRules(),
      files: listRuleFiles(),
    };
  }
  if (name === "get_rule") {
    const id = String(argumentsObject.rule_id ?? argumentsObject.file ?? "");
    return getRule(id);
  }
  if (name === "get_constraints") {
    const ruleIds = Array.isArray(argumentsObject.rule_ids) ? argumentsObject.rule_ids : undefined;
    return getConstraints(ruleIds);
  }
  if (name === "get_feature_rules") {
    const featureType = String(argumentsObject.feature_type ?? "general");
    const capabilityTags = Array.isArray(argumentsObject.capability_tags) ? argumentsObject.capability_tags.map((item) => String(item)) : [];
    const ruleFiles = Array.isArray(argumentsObject.rule_files) ? argumentsObject.rule_files.map((item) => String(item)) : undefined;
    const payload = getFeatureRules(featureType, capabilityTags, ruleFiles);
    return {
      ...payload,
      rule_contents: payload.rules.reduce((acc, rule) => {
        acc[rule.file] = readRuleContent(rule.file);
        return acc;
      }, {} as Record<string, string>),
    };
  }
  if (name === "get_layering_semantics") {
    return getLayeringSemantics();
  }
  throw new Error(`未知工具: ${name}`);
}

function runCli(tool: string, argumentsText?: string): void {
  const payload = toolDispatch(tool, parseArguments(argumentsText));
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
    {
      name: "get_layering_semantics",
      description: "返回架构分层语义及调用方向规则 (JSON 格式)",
      inputSchema: {
        type: "object",
        properties: {},
      },
    },
  ];
}

function writeJsonRpc(id: unknown, result: JsonRecord, isError = false): void {
  const message: JsonRecord = { jsonrpc: "2.0", id, result };
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
