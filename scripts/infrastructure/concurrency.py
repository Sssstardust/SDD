#!/usr/bin/env python3
"""
Lightweight file locking and atomic write helpers for local-first workflows.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from ._root import ROOT


LOCKS_DIR = ROOT / ".spec" / "locks"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sanitize_lock_label(value: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-._").lower()
    return sanitized or "resource"


def _lock_name_for_path(path: Path, *, prefix: str) -> str:
    resolved = path.resolve()
    suffix = hashlib.sha1(str(resolved).encode("utf-8")).hexdigest()[:8]
    return f"{prefix}-{_sanitize_lock_label(resolved.name or 'root')}-{suffix}.lock"


def _feature_lock_name(feature_dir: Path) -> str:
    return f"{feature_dir.resolve().name}.lock"


def feature_lock_path(feature_dir: Path) -> Path:
    LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    return LOCKS_DIR / _feature_lock_name(feature_dir)


def path_lock_path(path: Path) -> Path:
    LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    return LOCKS_DIR / _lock_name_for_path(path, prefix="path")


def _serialize_lock_payload(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _read_lock_payload(lock_path: Path) -> dict[str, object] | None:
    if not lock_path.exists():
        return None
    try:
        return json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _is_expired(payload: dict[str, object] | None) -> bool:
    if not isinstance(payload, dict):
        return True
    expires_at = payload.get("expires_at")
    if not isinstance(expires_at, str):
        return True
    try:
        return _utc_now() >= datetime.fromisoformat(expires_at)
    except ValueError:
        return True


def _lock_payload(resource: dict[str, object], owner: str, *, ttl_seconds: int, phase: str) -> dict[str, object]:
    locked_at = _utc_now()
    expires_at = locked_at + timedelta(seconds=ttl_seconds)
    return {
        **resource,
        "locked_by": owner,
        "phase": phase,
        "locked_at": locked_at.isoformat(),
        "expires_at": expires_at.isoformat(),
    }


@contextmanager
def _acquire_lock(
    lock_path: Path,
    payload: dict[str, object],
    *,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> Iterator[Path]:
    deadline = time.monotonic() + timeout_seconds

    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, _serialize_lock_payload(payload).encode("utf-8"))
            finally:
                os.close(fd)
            break
        except FileExistsError:
            existing = _read_lock_payload(lock_path)
            if _is_expired(existing):
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    pass
                continue
            if time.monotonic() >= deadline:
                holder = existing.get("locked_by") if isinstance(existing, dict) else "unknown"
                raise TimeoutError(f"lock busy: {lock_path.name} held by {holder}")
            time.sleep(poll_interval_seconds)

    try:
        yield lock_path
    finally:
        current = _read_lock_payload(lock_path)
        if isinstance(current, dict) and current.get("locked_by") == payload.get("locked_by"):
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass


@contextmanager
def feature_lock(
    feature_dir: Path,
    *,
    owner: str | None = None,
    phase: str = "unknown",
    timeout_seconds: float = 10.0,
    ttl_seconds: int = 1800,
    poll_interval_seconds: float = 0.1,
) -> Iterator[Path]:
    lock_path = feature_lock_path(feature_dir)
    effective_owner = owner or f"local-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    payload = _lock_payload(
        {
            "feature_id": feature_dir.name,
            "feature_dir": str(feature_dir.resolve()),
        },
        effective_owner,
        ttl_seconds=ttl_seconds,
        phase=phase,
    )
    with _acquire_lock(
        lock_path,
        payload,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    ) as acquired:
        yield acquired


@contextmanager
def path_lock(
    path: Path,
    *,
    owner: str | None = None,
    phase: str = "unknown",
    timeout_seconds: float = 10.0,
    ttl_seconds: int = 1800,
    poll_interval_seconds: float = 0.1,
) -> Iterator[Path]:
    resolved = path.resolve()
    lock_path = path_lock_path(resolved)
    effective_owner = owner or f"local-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    payload = _lock_payload(
        {
            "path": str(resolved),
            "path_name": resolved.name or str(resolved),
        },
        effective_owner,
        ttl_seconds=ttl_seconds,
        phase=phase,
    )
    with _acquire_lock(
        lock_path,
        payload,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    ) as acquired:
        yield acquired


def atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        last_error: OSError | None = None
        for attempt in range(15):
            try:
                os.replace(temp_path, path)
                last_error = None
                break
            except OSError as error:
                last_error = error
                if attempt >= 14:
                    raise
                time.sleep(0.2 * (attempt + 1))
        if last_error is not None:
            raise last_error
    finally:
        try:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        except OSError:
            pass

