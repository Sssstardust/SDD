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
exports.wantsAsync = wantsAsync;
exports.shouldRunAsyncByDefault = shouldRunAsyncByDefault;
exports.implementationSummaryFromReport = implementationSummaryFromReport;
exports.toolDispatch = toolDispatch;
exports.main = main;
const fs = __importStar(require("node:fs"));
const path = __importStar(require("node:path"));
const readline = __importStar(require("node:readline"));
const node_crypto_1 = require("node:crypto");
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
        inputSchema: {
            type: "object",
            properties: {
                async: { type: "boolean" },
            },
        },
    },
    {
        name: "project_console_cycle",
        description: "Refresh project state and regenerate project console artifacts.",
        inputSchema: {
            type: "object",
            properties: {
                async: { type: "boolean" },
            },
        },
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
                async: { type: "boolean" },
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
                async: { type: "boolean" },
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
                async: { type: "boolean" },
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
                async: { type: "boolean" },
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
                async: { type: "boolean" },
            },
        },
    },
    {
        name: "start_pipeline_task",
        description: "Start a detached asynchronous run_pipeline task and return a task id for polling.",
        inputSchema: {
            type: "object",
            properties: {
                pipeline_args: { type: "array", items: { type: "string" } },
                task_label: { type: "string" },
            },
            required: ["pipeline_args"],
        },
    },
    {
        name: "get_pipeline_task",
        description: "Read the current state of an asynchronous pipeline task.",
        inputSchema: {
            type: "object",
            properties: {
                task_id: { type: "string" },
            },
            required: ["task_id"],
        },
    },
    {
        name: "read_pipeline_task_result",
        description: "Read the structured result of a completed asynchronous pipeline task.",
        inputSchema: {
            type: "object",
            properties: {
                task_id: { type: "string" },
            },
            required: ["task_id"],
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
const TASKS_DIR = path.join(ROOT, ".spec", "tasks");
const TASK_RUNNER = path.join(__dirname, "task-runner.js");
let RESOLVED_PYTHON_COMMAND = null;
function getPythonCommand() {
    return process.env.SDD_PYTHON || "python";
}
function resolvedPythonCommand() {
    if (RESOLVED_PYTHON_COMMAND) {
        return RESOLVED_PYTHON_COMMAND;
    }
    const preferred = getPythonCommand();
    const probe = (0, node_child_process_1.spawnSync)(preferred, ["-c", "import sys; print(sys.executable)"], {
        cwd: ROOT,
        encoding: "utf8",
    });
    const resolved = (probe.stdout || "").trim().split(/\r?\n/, 1)[0];
    if (resolved) {
        RESOLVED_PYTHON_COMMAND = resolved;
        return RESOLVED_PYTHON_COMMAND;
    }
    const whereProbe = (0, node_child_process_1.spawnSync)("where.exe", [preferred], {
        cwd: ROOT,
        encoding: "utf8",
    });
    const whereResolved = (whereProbe.stdout || "").trim().split(/\r?\n/, 1)[0];
    RESOLVED_PYTHON_COMMAND = whereResolved || preferred;
    return RESOLVED_PYTHON_COMMAND;
}
function parseStructuredPipelineOutput(rawStdout) {
    const trimmed = rawStdout.trim();
    if (!trimmed) {
        return null;
    }
    try {
        const parsed = JSON.parse(trimmed);
        if (typeof parsed.status === "string" && typeof parsed.message === "string") {
            return parsed;
        }
    }
    catch {
        return null;
    }
    return null;
}
function runPipeline(args) {
    const command = [resolvedPythonCommand(), RUN_PIPELINE, "--json", ...args];
    const result = (0, node_child_process_1.spawnSync)(command[0], command.slice(1), {
        cwd: ROOT,
        encoding: "utf8",
    });
    const spawnError = result.error;
    const structured = parseStructuredPipelineOutput(result.stdout || "");
    const structuredStatus = typeof structured?.status === "string" ? structured.status : null;
    return {
        ok: structuredStatus ? structuredStatus !== "error" : result.status === 0,
        exit_code: result.status ?? -1,
        signal: result.signal ?? null,
        command,
        stdout: result.stdout || "",
        stderr: result.stderr || "",
        error_code: spawnError?.code ?? null,
        error_message: spawnError?.message ?? null,
        execution_blocked: spawnError?.code === "EPERM",
        structured_output: structured,
        status: structuredStatus ?? (result.status === 0 ? "ok" : "error"),
        message: typeof structured?.message === "string" ? structured.message : null,
        warnings: Array.isArray(structured?.warnings) ? structured.warnings : [],
        errors: Array.isArray(structured?.errors) ? structured.errors : [],
        artifacts: structured?.artifacts ?? {},
    };
}
function readJsonFile(filePath) {
    if (!fs.existsSync(filePath)) {
        return null;
    }
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
}
function writeJsonFile(filePath, payload) {
    fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
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
function wantsAsync(argumentsObject, defaultAsync = false) {
    if (argumentsObject.async === true) {
        return true;
    }
    if (argumentsObject.async === false) {
        return false;
    }
    return defaultAsync;
}
function shouldRunAsyncByDefault(toolName) {
    return new Set([
        "refresh_baseline",
        "project_console_cycle",
        "validate_all_reports",
        "design_gates",
        "gate5",
        "release_gate",
        "onboard_project",
    ]).has(toolName);
}
function ensureTasksDir() {
    fs.mkdirSync(TASKS_DIR, { recursive: true });
}
function createTaskId() {
    return `task-${Date.now()}-${(0, node_crypto_1.randomBytes)(4).toString("hex")}`;
}
function resolveTaskId(value) {
    if (typeof value !== "string" || !/^task-[a-zA-Z0-9-]+$/.test(value)) {
        throw new Error("task_id is required and must be a valid task identifier");
    }
    return value;
}
function taskPaths(taskId) {
    const taskDir = path.join(TASKS_DIR, taskId);
    return {
        task_dir: taskDir,
        task_file: path.join(taskDir, "task.json"),
        result_file: path.join(taskDir, "result.json"),
        stdout_file: path.join(taskDir, "stdout.log"),
        stderr_file: path.join(taskDir, "stderr.log"),
    };
}
function readTaskState(taskId) {
    const paths = taskPaths(taskId);
    return readJsonFile(String(paths.task_file));
}
function startPipelineTask(pipelineArgs, taskLabel) {
    if (!Array.isArray(pipelineArgs) || pipelineArgs.length === 0) {
        throw new Error("pipeline_args must contain at least one run_pipeline command");
    }
    ensureTasksDir();
    const taskId = createTaskId();
    const paths = taskPaths(taskId);
    fs.mkdirSync(String(paths.task_dir), { recursive: true });
    const createdAt = new Date().toISOString();
    const taskPayload = {
        task_id: taskId,
        task_label: taskLabel || pipelineArgs.join(" "),
        status: "queued",
        created_at: createdAt,
        updated_at: createdAt,
        pipeline_args: pipelineArgs,
        command: [resolvedPythonCommand(), RUN_PIPELINE, "--json", ...pipelineArgs],
        task_dir: paths.task_dir,
        task_file: paths.task_file,
        result_file: paths.result_file,
        stdout_file: paths.stdout_file,
        stderr_file: paths.stderr_file,
    };
    writeJsonFile(String(paths.task_file), taskPayload);
    const runnerArgs = [
        TASK_RUNNER,
        "--task-file",
        String(paths.task_file),
        "--result-file",
        String(paths.result_file),
        "--stdout-file",
        String(paths.stdout_file),
        "--stderr-file",
        String(paths.stderr_file),
        "--python",
        resolvedPythonCommand(),
        "--run-pipeline",
        RUN_PIPELINE,
        "--cwd",
        ROOT,
        "--",
        ...pipelineArgs,
    ];
    const child = (0, node_child_process_1.spawn)(process.execPath, runnerArgs, {
        cwd: ROOT,
        detached: true,
        stdio: "ignore",
    });
    child.unref();
    taskPayload.runner_pid = child.pid ?? null;
    taskPayload.updated_at = new Date().toISOString();
    writeJsonFile(String(paths.task_file), taskPayload);
    return {
        ok: true,
        status: "accepted",
        message: `Started async pipeline task ${taskId}`,
        task_id: taskId,
        task: taskPayload,
        poll_hint: {
            tool: "get_pipeline_task",
            arguments: { task_id: taskId },
        },
        result_hint: {
            tool: "read_pipeline_task_result",
            arguments: { task_id: taskId },
        },
    };
}
function withArtifactStatus(execution, artifact) {
    return {
        ...execution,
        artifact_status: execution.ok ? "refreshed" : artifact ? "fallback-existing" : "missing",
    };
}
function implementationSummaryFromReport(report) {
    if (!report || typeof report !== "object") {
        return {
            implementation_result: null,
            implementation_framework_evidence: {},
            implementation_match_highlights: [],
        };
    }
    const frameworkEvidence = report.implementation_method_framework_evidence && typeof report.implementation_method_framework_evidence === "object"
        ? report.implementation_method_framework_evidence
        : report.implementation_framework_evidence && typeof report.implementation_framework_evidence === "object"
            ? report.implementation_framework_evidence
            : {};
    const matchHighlights = Array.isArray(report.implementation_method_match_highlights)
        ? report.implementation_method_match_highlights
        : Array.isArray(report.implementation_match_highlights)
            ? report.implementation_match_highlights
            : [];
    return {
        implementation_result: typeof report.implementation_result === "string" ? report.implementation_result : null,
        implementation_framework_evidence: frameworkEvidence,
        implementation_match_highlights: matchHighlights,
        gate5_admission_summary: report.gate5_admission_summary && typeof report.gate5_admission_summary === "object"
            ? report.gate5_admission_summary
            : {},
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
        if (wantsAsync(argumentsObject, shouldRunAsyncByDefault(name))) {
            return startPipelineTask(["refresh-baseline"], "refresh_baseline");
        }
        const execution = runPipeline(["refresh-baseline"]);
        return {
            ...execution,
            attachment: readJsonFile(DEFAULT_ATTACHMENT_PATH),
        };
    }
    if (name === "project_console_cycle") {
        if (wantsAsync(argumentsObject, shouldRunAsyncByDefault(name))) {
            return startPipelineTask(["project-console-cycle"], "project_console_cycle");
        }
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
            project_console_features: Array.isArray(projectConsole?.features) ? projectConsole.features : [],
            workspace: projectConsole?.workspace && typeof projectConsole.workspace === "object" ? projectConsole.workspace : {},
            strict_recommended_count: typeof projectConsole?.strict_recommended_count === "number" ? projectConsole.strict_recommended_count : 0,
            strict_next_step_count: typeof projectConsole?.strict_next_step_count === "number" ? projectConsole.strict_next_step_count : 0,
            strict_summary: projectConsole?.strict_summary && typeof projectConsole.strict_summary === "object"
                ? projectConsole.strict_summary
                : {},
            gate_summary: projectConsole?.gate_summary && typeof projectConsole.gate_summary === "object"
                ? projectConsole.gate_summary
                : {},
            gate3_ai_review: projectConsole?.candidate?.gate3_ai_review && typeof projectConsole.candidate.gate3_ai_review === "object"
                ? projectConsole.candidate.gate3_ai_review
                : {},
        };
    }
    if (name === "project_next") {
        const execution = runPipeline(["project-next"]);
        const projectNextPath = latestArtifactFile("project-next.json");
        const projectNext = projectNextPath ? readJsonFile(projectNextPath) : null;
        return {
            ...withArtifactStatus(execution, projectNext),
            project_next_path: projectNextPath,
            project_next: projectNext,
            strict_recommended: projectNext?.candidate?.strict_recommended === true,
            strict_next_step: projectNext?.candidate?.strict_next_step === true,
            strict_summary: projectNext?.candidate?.strict_summary && typeof projectNext.candidate.strict_summary === "object"
                ? projectNext.candidate.strict_summary
                : {},
            gate_summary: projectNext?.gate_summary && typeof projectNext.gate_summary === "object"
                ? projectNext.gate_summary
                : {},
            project_highlights: projectNext?.project_highlights && typeof projectNext.project_highlights === "object"
                ? projectNext.project_highlights
                : {},
            gate3_ai_review: projectNext?.candidate?.gate3_ai_review && typeof projectNext.candidate.gate3_ai_review === "object"
                ? projectNext.candidate.gate3_ai_review
                : {},
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
            strict_recommended: flowStatus?.strict_recommended === true,
            strict_next_step: flowStatus?.strict_next_step === true,
            strict_summary: flowStatus?.strict_summary && typeof flowStatus.strict_summary === "object"
                ? flowStatus.strict_summary
                : {},
            gate3_rule_evaluation: flowStatus?.gate3_rule_evaluation && typeof flowStatus.gate3_rule_evaluation === "object"
                ? flowStatus.gate3_rule_evaluation
                : {},
            implementation_result: typeof flowStatus?.implementation_result === "string" ? flowStatus.implementation_result : null,
            implementation_framework_evidence: flowStatus?.implementation_framework_evidence && typeof flowStatus.implementation_framework_evidence === "object"
                ? flowStatus.implementation_framework_evidence
                : {},
            implementation_match_highlights: Array.isArray(flowStatus?.implementation_match_highlights)
                ? flowStatus.implementation_match_highlights
                : [],
            gate3_ai_review: flowStatus?.gate3_ai_review && typeof flowStatus.gate3_ai_review === "object"
                ? flowStatus.gate3_ai_review
                : {},
            gate5_admission_summary: flowStatus?.gate5_admission_summary && typeof flowStatus.gate5_admission_summary === "object"
                ? flowStatus.gate5_admission_summary
                : {},
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
        if (wantsAsync(argumentsObject, shouldRunAsyncByDefault(name))) {
            return startPipelineTask(args, "validate_all_reports");
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
        if (wantsAsync(argumentsObject, shouldRunAsyncByDefault(name))) {
            return startPipelineTask(args, "design_gates");
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
        if (wantsAsync(argumentsObject, shouldRunAsyncByDefault(name))) {
            return startPipelineTask(args, "gate5");
        }
        const execution = runPipeline(args);
        const reportsDir = path.join(featureDir, "reports");
        const verifyReportPath = findLatestVersionedReport(reportsDir, "verify-report.json");
        const verifyReport = verifyReportPath ? readJsonFile(verifyReportPath) : null;
        return {
            ...withArtifactStatus(execution, verifyReport),
            verify_report_path: verifyReportPath,
            verify_report: verifyReport,
            ...implementationSummaryFromReport(verifyReport),
        };
    }
    if (name === "release_gate") {
        const featureDir = resolveFeatureDir(argumentsObject.feature_dir);
        const args = ["release-gate", featureDir];
        if (argumentsObject.strict === true) {
            args.push("--strict");
        }
        if (wantsAsync(argumentsObject, shouldRunAsyncByDefault(name))) {
            return startPipelineTask(args, "release_gate");
        }
        const execution = runPipeline(args);
        const reportsDir = path.join(featureDir, "reports");
        const reportPath = findLatestVersionedReport(reportsDir, "release-gate-report.json");
        const releaseGateReport = reportPath ? readJsonFile(reportPath) : null;
        return {
            ...withArtifactStatus(execution, releaseGateReport),
            release_gate_report_path: reportPath,
            release_gate_report: releaseGateReport,
            ...implementationSummaryFromReport(releaseGateReport),
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
        if (wantsAsync(argumentsObject, shouldRunAsyncByDefault(name))) {
            return startPipelineTask(args, "onboard_project");
        }
        const execution = runPipeline(args);
        return {
            ...execution,
            attachment_path: DEFAULT_ATTACHMENT_PATH,
            attachment: readJsonFile(DEFAULT_ATTACHMENT_PATH),
        };
    }
    if (name === "start_pipeline_task") {
        const pipelineArgs = asStringArray(argumentsObject.pipeline_args);
        const taskLabel = typeof argumentsObject.task_label === "string" ? argumentsObject.task_label : undefined;
        return startPipelineTask(pipelineArgs, taskLabel);
    }
    if (name === "get_pipeline_task") {
        const taskId = resolveTaskId(argumentsObject.task_id);
        const task = readTaskState(taskId);
        if (!task) {
            return {
                ok: false,
                status: "missing",
                message: `Task not found: ${taskId}`,
                task_id: taskId,
            };
        }
        const paths = taskPaths(taskId);
        return {
            ok: task.status !== "failed",
            status: task.status,
            message: `Task ${taskId} is ${task.status}`,
            task_id: taskId,
            task,
            has_result: fs.existsSync(String(paths.result_file)),
        };
    }
    if (name === "read_pipeline_task_result") {
        const taskId = resolveTaskId(argumentsObject.task_id);
        const task = readTaskState(taskId);
        if (!task) {
            return {
                ok: false,
                status: "missing",
                message: `Task not found: ${taskId}`,
                task_id: taskId,
            };
        }
        const paths = taskPaths(taskId);
        const resultPayload = readJsonFile(String(paths.result_file));
        if (!resultPayload) {
            return {
                ok: false,
                status: "pending",
                message: `Task ${taskId} has not produced a result yet`,
                task_id: taskId,
                task,
            };
        }
        return {
            ok: task.status !== "failed",
            status: task.status,
            message: `Loaded result for task ${taskId}`,
            task_id: taskId,
            task,
            result: resultPayload,
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
if (require.main === module) {
    main();
}
