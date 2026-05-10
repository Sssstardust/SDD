#!/usr/bin/env python3
"""
Entrypoint bridge for run_pipeline main.
"""

from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from run_pipeline import main


if __name__ == "__main__":
    raise SystemExit(main())

