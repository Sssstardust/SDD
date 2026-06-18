#!/usr/bin/env python3
import argparse
import sys
import time
from pathlib import Path

# 动态扩展 PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sdd_core.application.cli.core import registry

from sdd_core.application.pipeline_facade import set_json_mode, console_print, build_json_payload, emit_result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", dest="json_output", action="store_true", help="emit structured JSON result")
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    registry.build_parsers(subparsers)

    args = parser.parse_args(argv)
    set_json_mode(args.json_output)

    start_time = time.perf_counter()
    exit_code = 0
    try:
        if hasattr(args, "func"):
            res = args.func(args)
            if isinstance(res, int):
                exit_code = res
        else:
            console_print(f"Command not implemented: {args.cmd}")
            exit_code = 1
    except Exception as exc:
        if not args.json_output:
            raise
        exit_code = 1
        console_print(f"[FATAL] {exc}")

    duration_ms = int((time.perf_counter() - start_time) * 1000)

    if args.json_output:
        if exit_code != 0:
            payload = build_json_payload(args, exit_code, duration_ms)
            emit_result(payload)
            return 1
        emit_result(build_json_payload(args, exit_code, duration_ms))
        return exit_code

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
