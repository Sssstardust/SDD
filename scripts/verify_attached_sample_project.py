#!/usr/bin/env python3
"""
Lightweight attached-project verification for the bundled sample project.
"""

from __future__ import annotations

import sys
from pathlib import Path


REQUIRED_FILES = [
    Path("src/main/java/com/example/paymentreviewcontrol/controller/PaymentReviewController.java"),
    Path("src/main/java/com/example/paymentreviewcontrol/service/PaymentReviewService.java"),
    Path("src/main/java/com/example/pricinglistcontrol/service/PricingService.java"),
    Path("src/main/resources/db/migration/V1__pricing_list_control.sql"),
]


def main() -> int:
    project_root = Path.cwd()
    missing = [path for path in REQUIRED_FILES if not (project_root / path).exists()]
    if missing:
        print("[FAIL] attached sample project verification failed")
        for path in missing:
            print(f"  - missing: {path.as_posix()}")
        return 1

    print("[OK] attached sample project verification passed")
    print(f"  - root: {project_root}")
    print(f"  - checked: {len(REQUIRED_FILES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
