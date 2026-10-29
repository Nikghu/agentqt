"""
Module: MD-BKT-002.005.M03 — backtest/cache.py
Parent SRD: SRD-BKT-002.005, SRD-BKT-002.006

Keyed step cache: ``<root>/<step>/<key>/<name>.parquet``. Writes are atomic
because the app, the CLI and (later) the MCP server share the cache.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from us_swing.backtest import DEFAULT_ROOT

DEFAULT_CACHE_ROOT: Path = DEFAULT_ROOT / "cache"
MAX_AGE_DAYS = 30
MAX_BYTES = 5 * 1024**3


def make_key(step: str, version: int, params: Any) -> str:
    """Return the sha256 key of a step's inputs; dict order does not matter."""
    text = json.dumps(
        {"step": step, "version": version, "params": params}, sort_keys=True, default=str
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class StepCache:
    """Read and write step outputs by key."""

    def __init__(self, root: Path = DEFAULT_CACHE_ROOT) -> None:
        self.root = root

    def _path(self, step: str, key: str, name: str) -> Path:
        return self.root / step / key / f"{name}.parquet"

    def read(self, step: str, key: str, name: str) -> pd.DataFrame | None:
        """Return the saved frame, or ``None`` on a miss; a hit marks the file used."""
        path = self._path(step, key, name)
        try:
            frame = pd.read_parquet(path)
        except FileNotFoundError:
            return None
        os.utime(path)
        return frame

    def write(self, step: str, key: str, name: str, frame: pd.DataFrame) -> None:
        """Save ``frame`` atomically under ``step/key/name``."""
        path = self._path(step, key, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{name}.{uuid.uuid4().hex}.tmp")
        try:
            frame.to_parquet(tmp, index=False)
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)

    def names(self, step: str, key: str) -> set[str]:
        """Return the names saved under ``step/key``."""
        folder = self.root / step / key
        if not folder.is_dir():
            return set()
        return {p.stem for p in folder.glob("*.parquet")}

    def cleanup(
        self, now: datetime, max_age_days: int = MAX_AGE_DAYS, max_bytes: int = MAX_BYTES
    ) -> int:
        """Delete files unused for ``max_age_days``, then the oldest over ``max_bytes``.

        Returns:
            Bytes freed.
        """
        files = sorted(
            ((p, p.stat()) for p in self.root.glob("*/*/*.parquet")),
            key=lambda item: item[1].st_mtime,
        )
        cutoff = now.timestamp() - max_age_days * 86_400
        total = sum(st.st_size for _, st in files)
        freed = 0
        for path, st in files:
            if st.st_mtime >= cutoff and total <= max_bytes:
                break
            path.unlink(missing_ok=True)
            total -= st.st_size
            freed += st.st_size
        for folder in self.root.glob("*/*"):
            if folder.is_dir() and not any(folder.iterdir()):
                shutil.rmtree(folder, ignore_errors=True)
        return freed
