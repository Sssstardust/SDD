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
const node_child_process_1 = require("node:child_process");
function parseArgs(argv) {
    const options = {};
    const pipelineArgs = [];
    let passthrough = false;
    for (let index = 0; index < argv.length; index += 1) {
        const current = argv[index];
        if (passthrough) {
            pipelineArgs.push(current);
            continue;
        }
        if (current === "--") {
            passthrough = true;
            continue;
        }
        if (!current.startsWith("--")) {
            continue;
        }
        const key = current.slice(2);
        const next = argv[index + 1];
        if (!next || next.startsWith("--")) {
            throw new Error(`Missing value for --${key}`);
        }
        options[key] = next;
        index += 1;
    }
    return { options, pipelineArgs };
}
function readJsonFile(filePath) {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
}
function writeJsonFile(filePath, payload) {
    fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
}
function updateTask(taskFile, patch) {
    const current = readJsonFile(taskFile);
    const next = {
        ...current,
        ...patch,
        updated_at: new Date().toISOString(),
    };
    writeJsonFile(taskFile, next);
    return next;
}
function parseStructuredResult(rawStdout) {
    const trimmed = rawStdout.trim();
    if (!trimmed) {
        return null;
    }
    try {
        return JSON.parse(trimmed);
    }
    catch {
        return null;
    }
}
function buildSubprocessEnv() {
    return {
        ...process.env,
        PYTHONIOENCODING: process.env.PYTHONIOENCODING || "utf-8",
        PYTHONUTF8: process.env.PYTHONUTF8 || "1",
    };
}
function main() {
    const { options, pipelineArgs } = parseArgs(process.argv.slice(2));
    const taskFile = options["task-file"];
    const resultFile = options["result-file"];
    const stdoutFile = options["stdout-file"];
    const stderrFile = options["stderr-file"];
    try {
        const pythonCommand = options["python"];
        const runPipeline = options["run-pipeline"];
        const cwd = options["cwd"] || path.dirname(path.dirname(runPipeline || ""));
        if (!taskFile || !resultFile || !stdoutFile || !stderrFile || !pythonCommand || !runPipeline) {
            throw new Error("task-runner missing required options");
        }
        updateTask(taskFile, {
            status: "running",
            started_at: new Date().toISOString(),
            runner_pid: process.pid,
        });
        const command = [pythonCommand, runPipeline, "--json", ...pipelineArgs];
        const result = (0, node_child_process_1.spawnSync)(command[0], command.slice(1), {
            cwd,
            encoding: "utf8",
            env: buildSubprocessEnv(),
            windowsHide: true,
        });
        const spawnError = result.error;
        fs.writeFileSync(stdoutFile, result.stdout || "", "utf8");
        fs.writeFileSync(stderrFile, result.stderr || "", "utf8");
        const structured = parseStructuredResult(result.stdout || "");
        const failed = (structured && structured.status === "error") || (result.status ?? 1) !== 0;
        const finalStatus = failed ? "failed" : "completed";
        const finishedAt = new Date().toISOString();
        const resultPayload = {
            task_id: readJsonFile(taskFile).task_id,
            status: finalStatus,
            exit_code: result.status ?? -1,
            signal: result.signal ?? null,
            command,
            error_code: spawnError?.code ?? null,
            error_message: spawnError?.message ?? null,
            structured_result: structured,
            stdout_file: stdoutFile,
            stderr_file: stderrFile,
            finished_at: finishedAt,
        };
        writeJsonFile(resultFile, resultPayload);
        updateTask(taskFile, {
            status: finalStatus,
            finished_at: finishedAt,
            exit_code: result.status ?? -1,
            signal: result.signal ?? null,
            error_code: spawnError?.code ?? null,
            error_message: spawnError?.message ?? null,
            result_file: resultFile,
            stdout_file: stdoutFile,
            stderr_file: stderrFile,
        });
    }
    catch (error) {
        const message = error instanceof Error ? `${error.name}: ${error.message}` : String(error);
        if (stderrFile) {
            fs.writeFileSync(stderrFile, `${message}\n`, "utf8");
        }
        if (taskFile && fs.existsSync(taskFile)) {
            updateTask(taskFile, {
                status: "failed",
                finished_at: new Date().toISOString(),
                runner_pid: process.pid,
                bootstrap_error: message,
            });
        }
        if (taskFile && resultFile && fs.existsSync(taskFile)) {
            const taskPayload = readJsonFile(taskFile);
            writeJsonFile(resultFile, {
                task_id: taskPayload.task_id,
                status: "failed",
                exit_code: -1,
                signal: null,
                command: null,
                structured_result: null,
                stdout_file: stdoutFile || null,
                stderr_file: stderrFile || null,
                finished_at: new Date().toISOString(),
                bootstrap_error: message,
            });
        }
        process.exitCode = 1;
    }
}
main();
