"""Module: MD-SCR-006.001.M13 — screener/storage.py
Parent SRD: SRD-SCR-008.001–005, SRD-SCR-014.001–002

ScreenerResultsStorage  — atomic save/load/list of dated run results.
FeatureCache            — per-symbol-per-day feature cache (24 h TTL).
APIUsageTracker         — Claude API token + cost logging ($50/month cap).
AITranscriptTurn        — single turn in an AI conversation transcript.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

_log = logging.getLogger(__name__)

INPUT_COST_PER_1K: float = 0.003
OUTPUT_COST_PER_1K: float = 0.009
_COST_THRESHOLD_USD: float = 50.0
_FEATURE_TTL_SECONDS: int = 86_400  # 24 h


# ---------------------------------------------------------------------------
# AITranscriptTurn  (SRD-SCR-014.001)
# ---------------------------------------------------------------------------

@dataclass
class AITranscriptTurn:
    """One turn in an AI provider conversation transcript.

    ``tokens_input`` and ``tokens_output`` are non-zero only for
    ``role="assistant"`` turns that correspond to an API call.
    """

    role: Literal["system", "user", "assistant", "tool_result"]
    content: str
    tool_name: str | None = None
    tokens_input: int = 0
    tokens_output: int = 0
    sent_at: str | None = None      # ISO-8601 UTC — when the message was dispatched
    received_at: str | None = None  # ISO-8601 UTC — when the response arrived
    response_time_ms: int = 0       # round-trip ms; non-zero on assistant turns only

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "tool_name": self.tool_name,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "sent_at": self.sent_at,
            "received_at": self.received_at,
            "response_time_ms": self.response_time_ms,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AITranscriptTurn":
        _VALID_ROLES = {"system", "user", "assistant", "tool_result"}
        role_raw = d.get("role", "")
        if role_raw not in _VALID_ROLES:
            raise ValueError(f"AITranscriptTurn: unknown role {role_raw!r}")
        return cls(
            role=role_raw,  # type: ignore[arg-type]
            content=d.get("content", ""),
            tool_name=d.get("tool_name"),
            tokens_input=int(d.get("tokens_input", 0)),
            tokens_output=int(d.get("tokens_output", 0)),
            sent_at=d.get("sent_at"),
            received_at=d.get("received_at"),
            response_time_ms=int(d.get("response_time_ms", 0)),
        )


# ---------------------------------------------------------------------------
# ScreenerRunResult
# ---------------------------------------------------------------------------

@dataclass
class ScreenerRunResult:
    """Result of one preset execution run.

    ``results`` maps each *passing* symbol to a metadata dict containing
    at minimum ``passed`` (bool) and ``score`` (float).
    Composite runs also include ``matching_groups`` (list[str]).
    ``ai_transcript`` holds the full AI conversation from Stage 3 (empty
    list when AI ranking was not used or failed).
    """

    preset_id: str
    run_timestamp: str  # ISO-8601: YYYY-MM-DDTHH:MM:SSZ
    execution_mode: str  # "manual" | "scheduled"
    results: dict[str, dict[str, Any]] = field(default_factory=dict)
    ai_transcript: list[AITranscriptTurn] = field(default_factory=list)
    candle_date: str | None = None  # last daily candle date screened (SRD-SCR-004.009)

    @property
    def date(self) -> str:
        """YYYY-MM-DD portion of run_timestamp."""
        return self.run_timestamp[:10]

    def to_dict(self) -> dict[str, Any]:
        return {
            "preset_id": self.preset_id,
            "run_timestamp": self.run_timestamp,
            "execution_mode": self.execution_mode,
            "results": self.results,
            "ai_transcript": [t.to_dict() for t in self.ai_transcript],
            "candle_date": self.candle_date,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ScreenerRunResult":
        return cls(
            preset_id=d["preset_id"],
            run_timestamp=d["run_timestamp"],
            execution_mode=d["execution_mode"],
            results=d.get("results", {}),
            ai_transcript=[
                AITranscriptTurn.from_dict(t)
                for t in d.get("ai_transcript", [])
            ],
            candle_date=d.get("candle_date"),
        )


# ---------------------------------------------------------------------------
# ScreenerResultsStorage
# ---------------------------------------------------------------------------

class ScreenerResultsStorage:
    """Persist and retrieve ScreenerRunResult objects as dated JSON files.

    Default root: ``~/.usswing/screener_results/``
    Per-preset layout: ``preset_{id}/{YYYY-MM-DD}.json``
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base = base_dir or Path.home() / ".usswing" / "screener_results"

    def _preset_dir(self, preset_id: str) -> Path:
        return self._base / f"preset_{preset_id}"

    def save_result(self, result: ScreenerRunResult, preset_id: str) -> Path:
        """Atomically write *result* to ``preset_{id}/{date}.json``.

        Uses a temp-then-rename strategy so partial writes are never visible.
        """
        out_dir = self._preset_dir(preset_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{result.date}.json"
        tmp_path = out_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        tmp_path.replace(out_path)
        return out_path

    def load_result(self, preset_id: str, date: str) -> ScreenerRunResult:
        """Load and deserialize the result for *preset_id* on *date*.

        Raises:
            FileNotFoundError: if no result file exists for that date.
            json.JSONDecodeError: if the file is corrupted.
        """
        path = self._preset_dir(preset_id) / f"{date}.json"
        if not path.exists():
            raise FileNotFoundError(
                f"No screener result for preset '{preset_id}' on {date}"
            )
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            _log.error("Corrupted result file: %s", path)
            raise
        return ScreenerRunResult.from_dict(data)

    def list_results(self, preset_id: str, limit: int = 30) -> list[str]:
        """Return up to *limit* result dates for *preset_id*, newest first.

        Returns date strings (YYYY-MM-DD), not ScreenerRunResult objects.
        """
        preset_dir = self._preset_dir(preset_id)
        if not preset_dir.exists():
            return []
        dates = sorted(
            [f.stem for f in preset_dir.glob("*.json") if not f.name.endswith(".tmp")],
            reverse=True,
        )
        return dates[:limit]

    def load_for_execution(
        self,
        preset_id: str,
        prefer_scheduled: bool = True,
    ) -> "ScreenerRunResult | None":
        """Return today's result for *preset_id*, or None if unavailable.

        If *prefer_scheduled* is True, only returns a result whose
        ``execution_mode`` equals ``"scheduled"`` — the auto-run produced
        when Enable Daily Scheduler is ON.  Returns None when today's result
        is manual-only or absent.

        If *prefer_scheduled* is False, returns any result for today
        regardless of execution_mode.

        Never raises; callers (e.g. the Execution module) can treat None as
        "no screener data available today".
        """
        from datetime import date as _date
        today = _date.today().isoformat()
        try:
            result = self.load_result(preset_id, today)
        except (FileNotFoundError, json.JSONDecodeError):
            return None
        if prefer_scheduled and result.execution_mode != "scheduled":
            return None
        return result


# ---------------------------------------------------------------------------
# FeatureCache
# ---------------------------------------------------------------------------

class FeatureCache:
    """Per-symbol-per-day feature cache with a 24 h TTL.

    Cache files: ``~/.usswing/screener_cache/features_{YYYY-MM-DD}.json``
    Each file is a dict[symbol → {features…, _cached_at: ISO-8601}].
    """

    def __init__(self, cache_dir: Path | None = None) -> None:
        self._dir = cache_dir or Path.home() / ".usswing" / "screener_cache"

    def _path(self, date: str) -> Path:
        return self._dir / f"features_{date}.json"

    def get(self, symbol: str, date: str | None = None) -> dict[str, Any] | None:
        """Return cached features for *symbol* on *date* if still fresh (< 24 h).

        Returns ``None`` if no cache entry exists or the entry is expired.
        """
        date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = self._path(date)
        if not path.exists():
            return None
        try:
            data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        entry = data.get(symbol)
        if entry is None:
            return None
        cached_at_str: str | None = entry.get("_cached_at")
        if cached_at_str:
            cached_at = datetime.fromisoformat(cached_at_str.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - cached_at).total_seconds()
            if age > _FEATURE_TTL_SECONDS:
                return None
        return {k: v for k, v in entry.items() if k != "_cached_at"}

    def set(self, symbol: str, features: dict[str, Any], date: str | None = None) -> None:
        """Store *features* for *symbol* on *date* with the current timestamp."""
        date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = self._path(date)
        self._dir.mkdir(parents=True, exist_ok=True)
        if path.exists():
            try:
                data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = {}
        else:
            data = {}
        data[symbol] = {
            **features,
            "_cached_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(path)


# ---------------------------------------------------------------------------
# APIUsageTracker
# ---------------------------------------------------------------------------

class APIUsageTracker:
    """Log Claude API token usage and enforce a $50/month cost cap.

    Usage log: ``~/.usswing/screener_api_usage.json``
    Cost formula: (tokens_in × 0.003 + tokens_out × 0.009) / 1000
    """

    def __init__(self, usage_file: Path | None = None) -> None:
        self._file = usage_file or Path.home() / ".usswing" / "screener_api_usage.json"

    def log_usage(
        self,
        tokens_in: int,
        tokens_out: int,
        preset_id: str = "",
    ) -> float:
        """Append a usage entry and return the cost in USD for this call.

        Emits a WARNING log if monthly total exceeds $50.
        """
        cost = (tokens_in * INPUT_COST_PER_1K + tokens_out * OUTPUT_COST_PER_1K) / 1000.0
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "preset_id": preset_id,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": cost,
        }
        self._file.parent.mkdir(parents=True, exist_ok=True)
        if self._file.exists():
            try:
                log: list[dict[str, Any]] = json.loads(
                    self._file.read_text(encoding="utf-8")
                )
            except json.JSONDecodeError:
                log = []
        else:
            log = []
        log.append(entry)
        self._file.write_text(json.dumps(log, indent=2), encoding="utf-8")

        # Compute monthly total from the already-in-memory log to avoid a
        # redundant disk read inside get_monthly_cost().
        prefix = datetime.now(timezone.utc).strftime("%Y-%m")
        monthly = sum(
            float(e.get("cost_usd", 0.0))
            for e in log
            if e.get("timestamp", "").startswith(prefix)
        )
        if monthly > _COST_THRESHOLD_USD:
            _log.warning(
                "APIUsageTracker: monthly cost $%.2f exceeds $%.0f threshold.",
                monthly,
                _COST_THRESHOLD_USD,
            )
        return cost

    def get_monthly_cost(self) -> float:
        """Return the total USD cost logged for the current calendar month."""
        if not self._file.exists():
            return 0.0
        try:
            log: list[dict[str, Any]] = json.loads(
                self._file.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            return 0.0
        prefix = datetime.now(timezone.utc).strftime("%Y-%m")
        return sum(
            float(e.get("cost_usd", 0.0))
            for e in log
            if e.get("timestamp", "").startswith(prefix)
        )
