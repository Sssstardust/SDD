#!/usr/bin/env python3
"""
Validate agent templates against the shared capability manifest.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST_PATH = ROOT / "templates" / "agent-capability-manifest.json"


def load_manifest(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"manifest must be a JSON object: {path}")
    return payload


def validate_templates(manifest: dict[str, object], root: Path = ROOT) -> dict[str, object]:
    required_snippets = manifest.get("required_snippets")
    templates = manifest.get("templates")
    if not isinstance(required_snippets, list) or not all(isinstance(item, str) for item in required_snippets):
        raise ValueError("required_snippets must be a string array")
    if not isinstance(templates, dict):
        raise ValueError("templates must be an object")

    results: list[dict[str, object]] = []
    errors: list[str] = []

    for template_name, raw_path in sorted(templates.items()):
        if not isinstance(raw_path, str):
            errors.append(f"{template_name}: template path must be a string")
            continue
        template_path = (root / raw_path).resolve()
        if not template_path.exists():
            errors.append(f"{template_name}: missing template file {template_path}")
            continue
        text = template_path.read_text(encoding="utf-8")
        missing = [snippet for snippet in required_snippets if snippet not in text]
        results.append(
            {
                "template": template_name,
                "path": str(template_path),
                "missing_snippets": missing,
                "status": "PASS" if not missing else "FAIL",
            }
        )
        if missing:
            errors.append(f"{template_name}: missing {len(missing)} required snippets")

    return {
        "manifest": str(DEFAULT_MANIFEST_PATH),
        "template_count": len(results),
        "results": results,
        "errors": errors,
        "status": "PASS" if not errors else "FAIL",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH), help="Path to template capability manifest")
    args = parser.parse_args(argv)

    payload = validate_templates(load_manifest(Path(args.manifest)))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
