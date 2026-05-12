#!/usr/bin/env node

import * as fs from "node:fs";
import * as path from "node:path";
import { spawnSync } from "node:child_process";

type JsonRecord = Record<string, any>;

function parseArgs(argv: string[]): { options: Record<string, string>; pipelineArgs: string[] } {
  const options: Record<string, string> = {};
  const pipelineArgs: string[] = [];
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

function readJsonFile(filePath: string): JsonRecord {
  return JSON.parse(fs.readFileSync(filePath, "utf8")) as JsonRecord;
}

function writeJsonFile(filePath: string, payload: JsonRecord): void {
  fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
}

function updateTask(taskFile: string, patch: JsonRecord): JsonRecord {
  const current = readJsonFile(taskFile);
  const next = {
    ...current,
    ...patch,
    updated_at: new Date().toISOString(),
  };
  writeJsonFile(taskFile, next);
  return next;
}

function parseStructuredResult(rawStdout: string): JsonRecord | null {
  const trimmed = rawStdout.trim();
  if (!trimmed) {
    return null;
  }
  try {
    return JSON.parse(trimmed) as JsonRecord;
  } catch {
    return null;
  }
}

function buildSubprocessEnv(): NodeJS.ProcessEnv {
  return {
    ...process.env,
    PYTHONIOENCODING: process.env.PYTHONIOENCODING || "utf-8",
    PYTHONUTF8: process.env.PYTHONUTF8 || "1",
  };
}

function main(): void {
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
    const result = spawnSync(command[0], command.slice(1), {
      cwd,
      encoding: "utf8",
      env: buildSubprocessEnv(),
      windowsHide: true,
    });
    const spawnError = result.error as NodeJS.ErrnoException | undefined;

    fs.writeFileSync(stdoutFile, result.stdout || "", "utf8");
    fs.writeFileSync(stderrFile, result.stderr || "", "utf8");

    const structured = parseStructuredResult(result.stdout || "");
    const failed = (structured && structured.status === "error") || (result.status ?? 1) !== 0;
    const finalStatus = failed ? "failed" : "completed";
    const finishedAt = new Date().toISOString();

    const resultPayload: JsonRecord = {
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
  } catch (error) {
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
