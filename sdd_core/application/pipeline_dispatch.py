#!/usr/bin/env python3
"""
Application-layer command dispatch helpers for run_pipeline.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable


def dispatch_command(args: argparse.Namespace, handlers: dict[str, Callable[[argparse.Namespace], int]]) -> int:
    handler = handlers.get(args.cmd)
    if handler is None:
        return 1
    return handler(args)
