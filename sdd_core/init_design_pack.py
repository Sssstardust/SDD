#!/usr/bin/env python3
import sys
from pathlib import Path

# 动态扩展 PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sdd_core.application.generators.init_design_pack import main

if __name__ == "__main__":
    raise SystemExit(main())
