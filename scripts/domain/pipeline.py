#!/usr/bin/env python3
"""
Domain model for pipeline run context.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PipelineRunContext:
    command: str
    feature_dir: Path | None = None
    strict: bool = False
    attachment_file: Path | None = None
    profile: str | None = None

    @property
    def feature_name(self) -> str | None:
        return self.feature_dir.name if isinstance(self.feature_dir, Path) else None

    def to_payload(self) -> dict[str, object]:
        return {
            "command": self.command,
            "feature_dir": str(self.feature_dir) if isinstance(self.feature_dir, Path) else None,
            "feature_name": self.feature_name,
            "strict": self.strict,
            "attachment_file": str(self.attachment_file) if isinstance(self.attachment_file, Path) else None,
            "profile": self.profile,
        }

