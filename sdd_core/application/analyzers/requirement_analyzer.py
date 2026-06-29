#!/usr/bin/env python3
"""
Deterministic extraction helpers for the requirement-analyzer skill.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.json"

