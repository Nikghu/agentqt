"""
Module: MD-EXE-015.007.M01 — execution/app_lock.py
Parent SRD: SRD-EXE-015.007, SRD-EXE-015.008

One-copy lock: only one running app may send orders. The app claims an
operating-system file lock at start; the system frees it when the app closes or
crashes, so a stale lock can never block the next start.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import IO

log = logging.getLogger(__name__)

LOCK_PATH = Path.home() / ".usswing" / "app.lock"


class OrderBlockedError(RuntimeError):
    """Raised when an order is stopped because this copy does not hold the lock."""


def _try_lock(handle: IO[bytes]) -> None:
    """Lock the file without waiting; raises ``OSError`` when another process holds it."""
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


class AppLock:
    """An exclusive lock on one file, held for the life of the app."""

    __slots__ = ("_path", "_file")

    def __init__(self, path: Path = LOCK_PATH) -> None:
        self._path = path
        self._file: IO[bytes] | None = None

    @property
    def held(self) -> bool:
        """True while this object holds the lock."""
        return self._file is not None

    def acquire(self) -> bool:
        """Take the lock; False when another copy of the app already has it."""
        if self._file is not None:
            return True
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self._path, "a+b")  # noqa: SIM115 — kept open while the lock is held
        try:
            _try_lock(handle)
        except OSError:
            handle.close()
            return False
        self._file = handle
        return True

    def release(self) -> None:
        """Give the lock back; closing the file frees it."""
        if self._file is not None:
            self._file.close()
            self._file = None


_claimed: AppLock | None = None


def claim_app_lock(path: Path = LOCK_PATH) -> bool:
    """Claim the one-copy lock for this app; False when another copy is running."""
    global _claimed
    lock = AppLock(path)
    if not lock.acquire():
        return False
    _claimed = lock
    return True


def check_order_allowed() -> None:
    """Stop an order when this app started with the lock but no longer holds it.

    Code that never claims the lock (tests, tools) is not blocked.

    Raises:
        OrderBlockedError: The lock was claimed and has been lost.
    """
    if _claimed is not None and not _claimed.held:
        log.error("[Orders] Another USSwing is running — order not sent")
        raise OrderBlockedError("another copy of USSwing is running")
