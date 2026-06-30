#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


SERVER_NAME = "sdd-pipeline"
SERVER_VERSION = "0.1.2"
ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / "sdd_core" / "run_pipeline.py"
DOCTOR = ROOT / "sdd_core" / "doctor.py"
PIPELINE_TIMEOUT_SECONDS = 120
LOG_PATH = ROOT / ".runtime" / "mcp-sdd-pipeline.log"


def _configure_stdio() -> None:
    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _log(message: str, **fields: Any) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "pid": os.getpid(),
            "version": SERVER_VERSION,
            "message": message,
            **fields,
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _feature_path(feature: str | None) -> str:
    if not feature:
        return str(ROOT / "specs")
    path = Path(feature)
    if path.is_absolute() or str(path).replace("\\", "/").startswith("specs/"):
        return str(path)
    return str(ROOT / "specs" / feature)


def _run_pipeline(args: list[str]) -> dict[str, Any]:
    cmd = [sys.executable, str(PIPELINE), "--json", *args]
    return _run_command(cmd, command=args[0] if args else "")


def _run_doctor() -> dict[str, Any]:
    cmd = [sys.executable, str(DOCTOR), "--json"]
    payload = _run_command(cmd, command="doctor")
    payload["stage"] = "doctor"
    return payload


def _run_command(cmd: list[str], *, command: str) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=_subprocess_env(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=PIPELINE_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "error",
            "blocking": True,
            "stage": command,
            "feature": None,
            "message": f"{command} timed out after {PIPELINE_TIMEOUT_SECONDS}s",
            "artifacts": [],
            "errors": [f"timeout after {PIPELINE_TIMEOUT_SECONDS}s"],
            "warnings": [],
            "next_action": {
                "type": "inspect_error",
                "target": command,
                "reason": "The SDD pipeline command exceeded the MCP timeout",
            },
            "raw": {
                "returncode": None,
                "payload": {},
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
            },
        }
    payload = _parse_json_payload(completed.stdout)

    normalized = _normalize_pipeline_payload(
        payload=payload,
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    return normalized


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    temp_dir = Path("C:/tmp")
    if not temp_dir.exists():
        temp_dir = ROOT
    for key in ("TMP", "TEMP", "TMPDIR"):
        env[key] = str(temp_dir)
    return env


def _parse_json_payload(stdout: str) -> dict[str, Any]:
    stripped = stdout.strip()
    if not stripped:
        return {}
    try:
        loaded = json.loads(stripped)
        return loaded if isinstance(loaded, dict) else {}
    except json.JSONDecodeError:
        pass
    for line in reversed(stdout.splitlines()):
        candidate = line.strip()
        if not candidate.startswith("{"):
            continue
        try:
            loaded = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        return loaded if isinstance(loaded, dict) else {}
    return {}


def _normalize_pipeline_payload(
    *,
    payload: dict[str, Any],
    command: str,
    returncode: int,
    stdout: str,
    stderr: str,
) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    errors = payload.get("errors") if isinstance(payload.get("errors"), list) else []
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    if not errors and isinstance(payload.get("sections"), list):
        errors = [
            str(section.get("message"))
            for section in payload["sections"]
            if isinstance(section, dict) and section.get("level") == "FAIL"
        ]
    if not warnings and isinstance(payload.get("sections"), list):
        warnings = [
            str(section.get("message"))
            for section in payload["sections"]
            if isinstance(section, dict) and section.get("level") == "WARN"
        ]
    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), list) else []
    status = payload.get("status")
    if status not in {"ok", "warn", "error"}:
        status = "ok" if returncode == 0 else "error"

    next_command = _extract_next_command(payload)
    message = payload.get("message") or (
        f"{command} completed" if returncode == 0 else f"{command} failed"
    )
    return {
        "status": status,
        "blocking": status == "error" or returncode != 0,
        "stage": data.get("stage") or command,
        "feature": data.get("feature") or data.get("feature_name"),
        "message": message,
        "artifacts": artifacts,
        "errors": errors,
        "warnings": warnings,
        "next_action": {
            "type": "run_command" if next_command else "inspect_result",
            "target": next_command,
            "reason": "Follow the SDD flow state's next command" if next_command else message,
        },
        "raw": {
            "returncode": returncode,
            "payload": payload,
            "stdout": stdout,
            "stderr": stderr,
        },
    }


def _extract_next_command(value: Any) -> str | None:
    if isinstance(value, dict):
        next_command = value.get("next_command")
        if isinstance(next_command, str) and next_command:
            return next_command
        for item in value.values():
            found = _extract_next_command(item)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _extract_next_command(item)
            if found:
                return found
    return None


def _tool_result(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, ensure_ascii=False, indent=2),
            }
        ],
        "isError": payload.get("status") == "error",
    }


def _read_json_file(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _state_path_for_feature(feature: str | None) -> Path:
    if feature:
        feature_path = Path(_feature_path(feature))
        preferred = feature_path / ".generated" / "project-state.json"
        return preferred if preferred.exists() else feature_path / "project-state.json"
    return ROOT / "specs" / "项目总览.json"


def _normalize_state_payload(state: dict[str, Any], *, feature: str | None, state_path: Path) -> dict[str, Any]:
    stage = str(
        state.get("current_stage")
        or state.get("stage")
        or state.get("current_recommendation", {}).get("stage")
        or "unknown"
    )
    next_command = state.get("next_command")
    if not isinstance(next_command, str) or not next_command:
        next_command = _extract_next_command(state)
    missing = state.get("missing_artifacts")
    blockers = state.get("blockers")
    warnings: list[str] = []
    if isinstance(missing, list) and missing:
        warnings.append(f"missing artifacts: {', '.join(str(item) for item in missing)}")
    if isinstance(blockers, list) and blockers:
        warnings.append(f"blockers: {', '.join(str(item) for item in blockers)}")
    return {
        "status": "ok",
        "blocking": bool(blockers),
        "stage": stage,
        "feature": feature or state.get("feature_name"),
        "message": f"flow state loaded from {state_path}",
        "artifacts": [str(state_path)],
        "errors": [],
        "warnings": warnings,
        "next_action": {
            "type": "run_command" if next_command else "inspect_result",
            "target": next_command,
            "reason": "Follow the SDD flow state's next command" if next_command else "No next command is required",
        },
        "raw": {
            "state_path": str(state_path),
            "state_summary": {
                "current_stage": stage,
                "risk_tier": state.get("risk_tier"),
                "gate2_result": state.get("gate2_result"),
                "gate3_result": state.get("gate3_result"),
                "gate4_result": state.get("gate4_result"),
                "gate5_result": state.get("gate5_result"),
                "implementation_result": state.get("implementation_result"),
                "release_gate_result": state.get("release_gate_result"),
            },
        },
    }


def _missing_state_payload(*, feature: str | None, state_path: Path) -> dict[str, Any]:
    return {
        "status": "error",
        "blocking": True,
        "stage": "inspect-flow",
        "feature": feature,
        "message": f"flow state file is missing: {state_path}",
        "artifacts": [],
        "errors": [f"missing flow state file: {state_path}"],
        "warnings": [],
        "next_action": {
            "type": "run_tool",
            "target": "sdd_continue_flow" if feature else "sdd_doctor",
            "reason": "Generate or refresh SDD state before inspecting it",
        },
        "raw": {"state_path": str(state_path)},
    }


def tool_sdd_doctor(arguments: dict[str, Any]) -> dict[str, Any]:
    payload = _run_doctor()
    return _tool_result(payload)


def tool_sdd_server_info(arguments: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "status": "ok",
        "blocking": False,
        "stage": "server-info",
        "feature": None,
        "message": f"{SERVER_NAME} {SERVER_VERSION} is running",
        "artifacts": [str(LOG_PATH)],
        "errors": [],
        "warnings": [],
        "next_action": {
            "type": "inspect_result",
            "target": None,
            "reason": "Server identity was loaded from the running MCP process",
        },
        "raw": {
            "server_name": SERVER_NAME,
            "server_version": SERVER_VERSION,
            "pid": os.getpid(),
            "root": str(ROOT),
            "server_path": str(Path(__file__).resolve()),
            "python": sys.executable,
            "log_path": str(LOG_PATH),
        },
    }
    return _tool_result(payload)


def tool_sdd_attach_project(arguments: dict[str, Any]) -> dict[str, Any]:
    cmd = ["attach-project"]
    project_root = arguments.get("project_root")
    if project_root:
        cmd.extend(["--project-root", str(project_root)])
    name = arguments.get("name")
    if name:
        cmd.extend(["--name", str(name)])
    for design_root in arguments.get("design_roots") or []:
        cmd.extend(["--design-root", str(design_root)])
    for schema_root in arguments.get("schema_roots") or []:
        cmd.extend(["--schema-root", str(schema_root)])
    profile = arguments.get("profile")
    if profile:
        cmd.extend(["--profile", str(profile)])
    payload = _run_pipeline(cmd)
    payload["stage"] = "attach-project"
    return _tool_result(payload)


def tool_sdd_inspect_flow(arguments: dict[str, Any]) -> dict[str, Any]:
    feature = str(arguments.get("feature") or "").strip() or None
    state_path = _state_path_for_feature(feature)
    state = _read_json_file(state_path)
    if state is None:
        payload = _missing_state_payload(feature=feature, state_path=state_path)
    else:
        payload = _normalize_state_payload(state, feature=feature, state_path=state_path)
    return _tool_result(payload)


def tool_sdd_bootstrap_feature(arguments: dict[str, Any]) -> dict[str, Any]:
    feature = str(arguments.get("feature") or "").strip()
    if not feature:
        return _tool_result(
            {
                "status": "error",
                "blocking": True,
                "stage": "bootstrap-feature",
                "feature": None,
                "message": "feature is required",
                "artifacts": [],
                "errors": ["feature is required"],
                "warnings": [],
                "next_action": {
                    "type": "ask_user",
                    "target": "feature",
                    "reason": "A feature name is required to bootstrap SDD artifacts",
                },
                "raw": {},
            }
        )
    cmd = ["init-feature", feature]
    payload = _run_pipeline(cmd)
    if payload["status"] != "error":
        boot = _run_pipeline(["bootstrap", _feature_path(feature)])
        payload = boot
    payload["stage"] = "bootstrap-feature"
    payload["feature"] = feature
    return _tool_result(payload)


def tool_sdd_validate_design(arguments: dict[str, Any]) -> dict[str, Any]:
    feature = str(arguments.get("feature") or "").strip()
    if not feature:
        return _tool_result(
            {
                "status": "error",
                "blocking": True,
                "stage": "validate-design",
                "feature": None,
                "message": "feature is required",
                "artifacts": [],
                "errors": ["feature is required"],
                "warnings": [],
                "next_action": {
                    "type": "ask_user",
                    "target": "feature",
                    "reason": "A feature name or specs path is required for validation",
                },
                "raw": {},
            }
        )
    cmd = ["validate", _feature_path(feature)]
    if arguments.get("strict"):
        cmd.append("--strict")
    payload = _run_pipeline(cmd)
    payload["stage"] = "validate-design"
    payload["feature"] = feature
    return _tool_result(payload)


def tool_sdd_continue_flow(arguments: dict[str, Any]) -> dict[str, Any]:
    feature = str(arguments.get("feature") or "").strip()
    if not feature:
        return _tool_result(
            {
                "status": "error",
                "blocking": True,
                "stage": "continue-flow",
                "feature": None,
                "message": "feature is required",
                "artifacts": [],
                "errors": ["feature is required"],
                "warnings": [],
                "next_action": {
                    "type": "ask_user",
                    "target": "feature",
                    "reason": "A feature name or specs path is required to continue the flow",
                },
                "raw": {},
            }
        )
    payload = _run_pipeline(["continue-flow", _feature_path(feature)])
    payload["stage"] = "continue-flow"
    payload["feature"] = feature
    return _tool_result(payload)


TOOLS = {
    "sdd_server_info": {
        "description": "Show the running sdd-pipeline MCP server version, PID, paths, and log file.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "handler": tool_sdd_server_info,
    },
    "sdd_doctor": {
        "description": "Check whether the local SDD pipeline can run.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "handler": tool_sdd_doctor,
    },
    "sdd_attach_project": {
        "description": "Attach a target project to the local SDD workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_root": {"type": "string"},
                "name": {"type": "string"},
                "design_roots": {"type": "array", "items": {"type": "string"}},
                "schema_roots": {"type": "array", "items": {"type": "string"}},
                "profile": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "handler": tool_sdd_attach_project,
    },
    "sdd_inspect_flow": {
        "description": "Inspect the current SDD project or feature flow state without refreshing it. Version: read-only-inspect.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "feature": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "handler": tool_sdd_inspect_flow,
    },
    "sdd_bootstrap_feature": {
        "description": "Initialize and bootstrap specs/<feature> for local SDD work.",
        "inputSchema": {
            "type": "object",
            "required": ["feature"],
            "properties": {
                "feature": {"type": "string"},
                "force": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
        "handler": tool_sdd_bootstrap_feature,
    },
    "sdd_validate_design": {
        "description": "Run SDD design validation, including Gate 1/2/3 where available.",
        "inputSchema": {
            "type": "object",
            "required": ["feature"],
            "properties": {
                "feature": {"type": "string"},
                "strict": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
        "handler": tool_sdd_validate_design,
    },
    "sdd_continue_flow": {
        "description": "Continue the current SDD feature flow by executing the next pipeline step.",
        "inputSchema": {
            "type": "object",
            "required": ["feature"],
            "properties": {
                "feature": {"type": "string"},
                "strict": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
        "handler": tool_sdd_continue_flow,
    },
}


def _send(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def _handle(request: dict[str, Any]) -> dict[str, Any] | None:
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params") if isinstance(request.get("params"), dict) else {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": name,
                        "description": meta["description"],
                        "inputSchema": meta["inputSchema"],
                    }
                    for name, meta in TOOLS.items()
                ]
            },
        }
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments")
        if not isinstance(arguments, dict):
            arguments = {}
        tool = TOOLS.get(str(name))
        if not tool:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": f"Unknown tool: {name}"},
            }
        try:
            _log("tool_call_start", tool=name, arguments=arguments)
            result = tool["handler"](arguments)
        except Exception as exc:
            _log("tool_call_error", tool=name, error=str(exc))
            result = _tool_result(
                {
                    "status": "error",
                    "blocking": True,
                    "stage": str(name),
                    "feature": arguments.get("feature"),
                    "message": str(exc),
                    "artifacts": [],
                    "errors": [str(exc)],
                    "warnings": [],
                    "next_action": {
                        "type": "inspect_error",
                        "target": str(name),
                        "reason": "MCP tool execution failed",
                    },
                    "raw": {},
                }
            )
        _log("tool_call_finish", tool=name, is_error=result.get("isError"))
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> int:
    _configure_stdio()
    _log("server_start", root=str(ROOT))
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            _log("request_decode_error", error=str(exc))
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": str(exc)},
                }
            )
            continue
        _log("request", method=request.get("method"), request_id=request.get("id"))
        response = _handle(request)
        if response is not None:
            _send(response)
            _log("response", method=request.get("method"), request_id=request.get("id"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
