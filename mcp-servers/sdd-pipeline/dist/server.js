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
const node_child_process_1 = require("node:child_process");
const PACKAGE = JSON.parse(fs.readFileSync(path.resolve(__dirname, "..", "package.json"), "utf8"));
const TOOL_DEFINITIONS = [
    {
        name: "list_pipeline_commands",
        description: "List the SDD pipeline tools exposed by this MCP server.",
        inputSchema: { type: "object", properties: {} },
    },
    {
        name: "show_attachment",
        description: "Read the current attached-project configuration.",
        inputSchema: { type: "object", properties: {} },
    },
    {
        name: "refresh_baseline",
        description: "Refresh module-map, schema-context, and baseline governance artifacts.",
        inputSchema: { type: "object", properties: {} },
    },
    {
        name: "project_console_cycle",
        description: "Refresh project state and regenerate project console artifacts.",
        inputSchema: { type: "object", properties: {} },
    },
    {
        name: "project_next",
        description: "Refresh and read the current project-next recommendation.",
        inputSchema: { type: "object", properties: {} },
    },
    {
        name: "flow_status",
        description: "Refresh and read flow-status for a feature directory.",
        inputSchema: {
            type: "object",
            properties: {
                feature_dir: { type: "string" },
            },
            required: ["feature_dir"],
        },
    },
    {
        name: "validate_reports",
        description: "Validate reports for a single feature.",
        inputSchema: {
            type: "object",
            properties: {
                feature_dir: { type: "string" },
                stage: { type: "string", enum: ["design", "implementation", "all"] },
            },
            required: ["feature_dir"],
        },
    },
    {
        name: "validate_all_reports",
        description: "Validate all known feature reports.",
        inputSchema: {
            type: "object",
            properties: {
                stage: { type: "string", enum: ["design", "implementation", "all"] },
                require_verify: { type: "boolean" },
            },
        },
    },
    {
        name: "generate_task_slices",
        description: "Generate task slices for a feature.",
        inputSchema: {
            type: "object",
            properties: {
                feature_dir: { type: "string" },
            },
            required: ["feature_dir"],
        },
    },
    {
        name: "design_gates",
        description: "Run the design-stage gates for a feature.",
        inputSchema: {
            type: "object",
            properties: {
                feature_dir: { type: "string" },
                strict: { type: "boolean" },
            },
            required: ["feature_dir"],
        },
    },
    {
        name: "gate5",
        description: "Run Gate 5 requirement coverage validation for a feature.",
        inputSchema: {
            type: "object",
            properties: {
                feature_dir: { type: "string" },
                strict: { type: "boolean" },
                require_attached_execution: { type: "boolean" },
            },
            required: ["feature_dir"],
        },
    },
    {
        name: "release_gate",
        description: "Run release-gate checks for a feature.",
        inputSchema: {
            type: "object",
            properties: {
                feature_dir: { type: "string" },
                strict: { type: "boolean" },
            },
            required: ["feature_dir"],
        },
    },
    {
        name: "onboard_project",
        description: "Attach a target project and run the onboarding chain.",
        inputSchema: {
            type: "object",
            properties: {
                project_root: { type: "string" },
                name: { type: "string" },
                design_roots: { type: "array", items: { type: "string" } },
                schema_roots: { type: "array", items: { type: "string" } },
                components_file: { type: "string" },
            },
        },
    },
];
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
            .replace(/'/g, "\"");
        return JSON.parse(normalized);
    }
}
function findRepoRoot(startDir) {
    let current = path.resolve(startDir);
    while (true) {
        const candidate = path.join(current, "scripts", "run_pipeline.py");
        if (fs.existsSync(candidate)) {
            return current;
        }
        const parent = path.dirname(current);
        if (parent === current) {
            throw new Error("Unable to locate repository root from sdd-pipeline MCP server");
        }
        current = parent;
    }
}
const ROOT = findRepoRoot(__dirname);
const RUN_PIPELINE = path.join(ROOT, "scripts", "run_pipeline.py");
const DEFAULT_ATTACHMENT_PATH = path.join(ROOT, ".spec", "attached-project.json");
const PROJECT_ARTIFACTS_DIR = path.join(ROOT, ".spec", "project-artifacts");
function getPythonCommand() {
    return process.env.SDD_PYTHON || "python";
}
function runPipeline(args) {
    const command = [getPythonCommand(), RUN_PIPELINE, ...args];
    const result = (0, node_child_process_1.spawnSync)(command[0], command.slice(1), {
        cwd: ROOT,
        encoding: "utf8",
    });
    const spawnError = result.error;
    return {
        ok: result.status === 0,
        exit_code: result.status ?? -1,
        signal: result.signal ?? null,
        command,
        stdout: result.stdout || "",
        stderr: result.stderr || "",
        error_code: spawnError?.code ?? null,
        error_message: spawnError?.message ?? null,
        execution_blocked: spawnError?.code === "EPERM",
    };
}
function readJsonFile(filePath) {
    if (!fs.existsSync(filePath)) {
        return null;
    }
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
}
function resolveFeatureDir(value) {
    if (typeof value !== "string" || !value.trim()) {
        throw new Error("feature_dir is required");
    }
    return path.resolve(ROOT, value);
}
function asStringArray(value) {
    return Array.isArray(value) ? value.filter((item) => typeof item === "string" && item.length > 0) : [];
}
function addRepeatedFlag(args, flag, values) {
    for (const value of values) {
        args.push(flag, value);
    }
}
function withArtifactStatus(execution, artifact) {
    return {
        ...execution,
        artifact_status: execution.ok ? "refreshed" : artifact ? "fallback-existing" : "missing",
    };
}
function latestArtifactFile(fileName) {
    if (!fs.existsSync(PROJECT_ARTIFACTS_DIR)) {
        return null;
    }
    const candidates = fs
        .readdirSync(PROJECT_ARTIFACTS_DIR, { withFileTypes: true })
        .filter((entry) => entry.isDirectory())
        .map((entry) => path.join(PROJECT_ARTIFACTS_DIR, entry.name, fileName))
        .filter((candidate) => fs.existsSync(candidate))
        .map((candidate) => ({
        path: candidate,
        mtimeMs: fs.statSync(candidate).mtimeMs,
    }))
        .sort((a, b) => b.mtimeMs - a.mtimeMs);
    return candidates[0]?.path || null;
}
function toolDispatch(name, argumentsObject) {
    if (name === "list_pipeline_commands") {
        return {
            count: TOOL_DEFINITIONS.length,
            tools: TOOL_DEFINITIONS.map((tool) => ({
                name: tool.name,
                description: tool.description,
            })),
        };
    }
    if (name === "show_attachment") {
        return {
            attachment_path: DEFAULT_ATTACHMENT_PATH,
            attachment: readJsonFile(DEFAULT_ATTACHMENT_PATH),
        };
    }
    if (name === "refresh_baseline") {
        const execution = runPipeline(["refresh-baseline"]);
        return {
            ...execution,
            attachment: readJsonFile(DEFAULT_ATTACHMENT_PATH),
        };
    }
    if (name === "project_console_cycle") {
        const execution = runPipeline(["project-console-cycle"]);
        const projectNextPath = latestArtifactFile("project-next.json");
        const projectConsolePath = latestArtifactFile("project-console.json");
        const projectNext = projectNextPath ? readJsonFile(projectNextPath) : null;
        const projectConsole = projectConsolePath ? readJsonFile(projectConsolePath) : null;
        return {
            ...withArtifactStatus(execution, projectNext ?? projectConsole),
            project_next_path: projectNextPath,
            project_next: projectNext,
            project_console_path: projectConsolePath,
            project_console: projectConsole,
        };
    }
    if (name === "project_next") {
        const execution = runPipeline(["project-next"]);
        const projectNextPath = latestArtifactFile("project-next.json");
        return {
            ...withArtifactStatus(execution, projectNextPath ? readJsonFile(projectNextPath) : null),
            project_next_path: projectNextPath,
            project_next: projectNextPath ? readJsonFile(projectNextPath) : null,
        };
    }
    if (name === "flow_status") {
        const featureDir = resolveFeatureDir(argumentsObject.feature_dir);
        const execution = runPipeline(["flow-status", featureDir]);
        const flowStatusPath = path.join(featureDir, "flow-status.json");
        const flowStatus = readJsonFile(flowStatusPath);
        return {
            ...withArtifactStatus(execution, flowStatus),
            flow_status_path: flowStatusPath,
            flow_status: flowStatus,
        };
    }
    if (name === "validate_reports") {
        const featureDir = resolveFeatureDir(argumentsObject.feature_dir);
        const stage = typeof argumentsObject.stage === "string" ? argumentsObject.stage : "all";
        return runPipeline(["validate-reports", featureDir, "--stage", stage]);
    }
    if (name === "validate_all_reports") {
        const stage = typeof argumentsObject.stage === "string" ? argumentsObject.stage : "all";
        const args = ["validate-all-reports", "--stage", stage];
        if (argumentsObject.require_verify === true) {
            args.push("--require-verify");
        }
        return runPipeline(args);
    }
    if (name === "generate_task_slices") {
        const featureDir = resolveFeatureDir(argumentsObject.feature_dir);
        const execution = runPipeline(["generate-task-slices", featureDir]);
        const generatedPath = path.join(featureDir, "tasks", "task-slices.generated.json");
        const taskSlices = readJsonFile(generatedPath);
        return {
            ...withArtifactStatus(execution, taskSlices),
            task_slices_path: generatedPath,
            task_slices: taskSlices,
        };
    }
    if (name === "design_gates") {
        const featureDir = resolveFeatureDir(argumentsObject.feature_dir);
        const args = ["design-gates", featureDir];
        if (argumentsObject.strict === true) {
            args.push("--strict");
        }
        return runPipeline(args);
    }
    if (name === "gate5") {
        const featureDir = resolveFeatureDir(argumentsObject.feature_dir);
        const args = ["gate5", featureDir];
        if (argumentsObject.require_attached_execution === true) {
            args.push("--require-attached-execution");
        }
        if (argumentsObject.strict === true) {
            args.push("--strict");
        }
        const execution = runPipeline(args);
        const reportsDir = path.join(featureDir, "reports");
        const verifyReportPath = findLatestVersionedReport(reportsDir, "verify-report.json");
        const verifyReport = verifyReportPath ? readJsonFile(verifyReportPath) : null;
        return {
            ...withArtifactStatus(execution, verifyReport),
            verify_report_path: verifyReportPath,
            verify_report: verifyReport,
        };
    }
    if (name === "release_gate") {
        const featureDir = resolveFeatureDir(argumentsObject.feature_dir);
        const args = ["release-gate", featureDir];
        if (argumentsObject.strict === true) {
            args.push("--strict");
        }
        const execution = runPipeline(args);
        const reportsDir = path.join(featureDir, "reports");
        const reportPath = findLatestVersionedReport(reportsDir, "release-gate-report.json");
        const releaseGateReport = reportPath ? readJsonFile(reportPath) : null;
        return {
            ...withArtifactStatus(execution, releaseGateReport),
            release_gate_report_path: reportPath,
            release_gate_report: releaseGateReport,
        };
    }
    if (name === "onboard_project") {
        const args = ["onboard-project"];
        if (typeof argumentsObject.project_root === "string") {
            args.push("--project-root", argumentsObject.project_root);
        }
        if (typeof argumentsObject.name === "string") {
            args.push("--name", argumentsObject.name);
        }
        addRepeatedFlag(args, "--design-root", asStringArray(argumentsObject.design_roots));
        addRepeatedFlag(args, "--schema-root", asStringArray(argumentsObject.schema_roots));
        if (typeof argumentsObject.components_file === "string") {
            args.push("--components-file", argumentsObject.components_file);
        }
        const execution = runPipeline(args);
        return {
            ...execution,
            attachment_path: DEFAULT_ATTACHMENT_PATH,
            attachment: readJsonFile(DEFAULT_ATTACHMENT_PATH),
        };
    }
    throw new Error(`Unknown tool: ${name}`);
}
function findLatestVersionedReport(reportsRoot, fileName) {
    if (!fs.existsSync(reportsRoot)) {
        return null;
    }
    const candidates = fs
        .readdirSync(reportsRoot, { withFileTypes: true })
        .filter((entry) => entry.isDirectory() && /^v\d+$/i.test(entry.name))
        .map((entry) => path.join(reportsRoot, entry.name, fileName))
        .filter((candidate) => fs.existsSync(candidate))
        .map((candidate) => ({
        path: candidate,
        mtimeMs: fs.statSync(candidate).mtimeMs,
    }))
        .sort((a, b) => b.mtimeMs - a.mtimeMs);
    return candidates[0]?.path || null;
}
function runCli(tool, argumentsText) {
    const payload = toolDispatch(tool, parseArguments(argumentsText));
    process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
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
        const id = message.id;
        const method = message.method;
        const params = message.params;
        try {
            if (method === "initialize") {
                writeJsonRpc(id, {
                    protocolVersion: typeof params?.protocolVersion === "string" ? params.protocolVersion : "2024-11-05",
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
                writeJsonRpc(id, { tools: TOOL_DEFINITIONS });
                return;
            }
            if (method === "tools/call") {
                const name = typeof params?.name === "string" ? params.name : "";
                const argumentsObject = params?.arguments || {};
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
