"""Module: MD-SCR-003.001.M10 — screener/executor.py
Parent SRD: SRD-SCR-003.001–008, SRD-SCR-013.006, SRD-SCR-013.007

PresetExecutor — orchestrates the 3-stage screening pipeline:
  Stage 1: PreFilter (price > $5, volume > 1 M)
  Stage 2: Parallel screener execution (composite or weighted logic)
  Stage 3: Optional LLM ranking via CloudAIScreener (AI tool-augmented
           when ``preset.ai_query`` is non-empty)
"""
from __future__ import annotations

import concurrent.futures
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Final

from us_swing.screener.base import PresetAccessDenied, ScreenerExecutionError
from us_swing.screener.preset import GroupLogic, Preset, PresetType
from us_swing.screener.registry import ScreenerRegistry
from us_swing.screener.storage import AITranscriptTurn, ScreenerResultsStorage, ScreenerRunResult
from us_swing.screener.utils import PreFilter

_log = logging.getLogger(__name__)

# Stage 3 input cap: the AI analyses at most _AI_MAX_INPUT stocks per run.
# When more pass Stage 2, only the top _AI_TOP_BY_CAP by market cap are sent.
_AI_MAX_INPUT: Final[int] = 20
_AI_TOP_BY_CAP: Final[int] = 10


class PresetExecutor:
    """Orchestrates the 3-stage screening pipeline for a single preset run.

    Dependencies are injectable to facilitate unit testing:
      - ``preset_manager``: must expose ``load_preset(preset_id, user_id) -> Preset``
      - ``db``:             must expose ``fetch_bars(symbols) -> dict[str, list]``
      - ``app_service``:    must expose ``get_universe_symbols() -> list[str]``
      - ``storage``:        ScreenerResultsStorage (defaults to prod path)
      - ``registry``:       ScreenerRegistry instance (defaults to global singleton)

    ``on_complete`` — optional callback invoked with the ScreenerRunResult after
    every successful run.

    ``notify`` — optional ``(level, message)`` callback for user-facing messages
    (e.g. the GUI log panel). Used to surface pipeline notices that would
    otherwise only reach the log file.
    """

    def __init__(
        self,
        db: Any = None,
        app_service: Any = None,
        preset_manager: Any = None,
        storage: ScreenerResultsStorage | None = None,
        registry: ScreenerRegistry | None = None,
        max_workers: int = 4,
        notify: Callable[[str, str], None] | None = None,
    ) -> None:
        self._db = db  # Any: duck-typed — must expose fetch_bars(symbols) -> dict
        self._app_service = app_service
        self._preset_manager = preset_manager
        self._storage = storage
        self._registry = registry
        self._max_workers = max_workers
        self._notify = notify
        self.on_complete: Callable[[ScreenerRunResult], None] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_preset(
        self,
        preset_id: str,
        user_id: str,
        manual: bool = True,
        *,
        symbols: list[str] | None = None,
        bars: dict[str, list[Any]] | None = None,
        preset: Preset | None = None,
        market_caps: dict[str, float] | None = None,
    ) -> ScreenerRunResult:
        """Execute a preset and persist the result.

        Args:
            preset_id: Identifier of the preset to run.
            user_id:   Requesting user — checked against preset permissions.
            manual:    True for on-demand runs, False for scheduled triggers.
            symbols:   Override universe symbols (useful in tests).
            bars:      Override bar data (useful in tests).
            preset:    Inject a Preset directly, bypassing preset_manager.
            market_caps: Per-symbol market cap (USD), used to pick the top
                         symbols when Stage 3 exceeds its input cap.

        Returns:
            ScreenerRunResult with only the passing symbols.

        Raises:
            PresetAccessDenied: if the user lacks access to the preset.
            ScreenerExecutionError: on unrecoverable pipeline failures.
        """
        # --- Load preset ---------------------------------------------------
        if preset is None:
            if self._preset_manager is None:
                raise ScreenerExecutionError(
                    "preset_manager is required when no preset is provided."
                )
            preset = self._preset_manager.load_preset(preset_id, user_id)

        # --- Universe + bars -----------------------------------------------
        if symbols is None:
            symbols = (
                self._app_service.get_universe_symbols()
                if self._app_service is not None
                else []
            )
        if bars is None:
            bars = (
                self._db.fetch_bars(symbols) if self._db is not None else {}
            )

        # --- Stage 1: PreFilter --------------------------------------------
        t0 = time.perf_counter()
        filtered = PreFilter().apply(symbols, bars)
        _log.debug(
            "Stage 1 pre-filter: %d/%d symbols in %.0f ms",
            len(filtered),
            len(symbols),
            (time.perf_counter() - t0) * 1000,
        )

        # --- Stage 2: Run screeners ----------------------------------------
        stage2 = self._run_stage2(preset, filtered, bars)

        # --- Combine per preset type ---------------------------------------
        combined = self._combine_results(preset, stage2, filtered)

        # --- Stage 3: LLM ranking (optional) ------------------------------
        ai_transcript: list[AITranscriptTurn] = []
        if preset.enable_llm_ranking:
            combined, ai_transcript = self._run_stage3(
                preset, combined, bars, market_caps,
            )

        # --- Enrich passing symbols with per-filter details ----------------
        registry = self._get_registry()
        all_refs = (
            [r for g in preset.groups for r in g.screeners if r.enabled]
            if preset.preset_type == PresetType.COMPOSITE
            else [r for r in preset.screeners if r.enabled]
        )
        passing_syms = [s for s, d in combined.items() if d.get("passed", False)]
        if passing_syms:
            for ref in all_refs:
                try:
                    screener = registry.get(ref.screener_id)
                    if hasattr(screener, "screen_detailed"):
                        detail_map = screener.screen_detailed(
                            passing_syms, bars, ref.config
                        )
                        for sym, det in detail_map.items():
                            if sym in combined:
                                existing = dict(combined[sym].get("details", {}))
                                existing.update(det)
                                combined[sym] = {**combined[sym], "details": existing}
                except Exception as exc:  # noqa: BLE001
                    _log.debug("screen_detailed failed for %s: %s", ref.screener_id, exc)

        # --- Build result (passing symbols only) ---------------------------
        passed = {
            sym: data
            for sym, data in combined.items()
            if data.get("passed", False)
        }
        result = ScreenerRunResult(
            preset_id=preset_id,
            run_timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            execution_mode="manual" if manual else "scheduled",
            results=passed,
            ai_transcript=ai_transcript,
        )

        # --- Persist + notify ----------------------------------------------
        self._get_storage().save_result(result, preset_id)
        if self.on_complete is not None:
            self.on_complete(result)

        return result

    # ------------------------------------------------------------------
    # Stage 2 — parallel screener execution
    # ------------------------------------------------------------------

    def _run_stage2(
        self,
        preset: Preset,
        symbols: list[str],
        bars: dict[str, list[Any]],
    ) -> dict[str, dict[str, tuple[bool, float]]]:
        """Call every enabled screener and collect per-symbol (passed, score).

        Returns:
            ``{screener_id: {symbol: (passed, score)}}``
        """
        registry = self._get_registry()

        # Collect unique enabled screener refs
        if preset.preset_type == PresetType.COMPOSITE:
            refs = [
                ref
                for group in preset.groups
                for ref in group.screeners
                if ref.enabled
            ]
        else:  # WEIGHTED
            refs = [r for r in preset.screeners if r.enabled]

        seen: set[str] = set()
        unique_refs = []
        for ref in refs:
            if ref.screener_id not in seen:
                seen.add(ref.screener_id)
                unique_refs.append(ref)

        if not unique_refs:
            return {}

        results: dict[str, dict[str, tuple[bool, float]]] = {}

        # All screeners run in ThreadPoolExecutor. asyncio.run() would raise
        # RuntimeError if an event loop is already running, and screener.apply()
        # is synchronous in every implementation, so asyncio provides no benefit.
        def _apply(ref: Any) -> tuple[str, dict[str, tuple[bool, float]]]:
            screener = registry.get(ref.screener_id)
            return ref.screener_id, screener.apply(symbols, bars, ref.config)

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self._max_workers
        ) as pool:
            for sid, res in pool.map(_apply, unique_refs):
                results[sid] = res

        return results

    # ------------------------------------------------------------------
    # Combine results per preset type
    # ------------------------------------------------------------------

    def _combine_results(
        self,
        preset: Preset,
        stage2: dict[str, dict[str, tuple[bool, float]]],
        symbols: list[str],
    ) -> dict[str, dict[str, Any]]:
        if preset.preset_type == PresetType.COMPOSITE:
            return self._composite_logic(preset, stage2, symbols)
        return self._weighted_logic(preset, stage2, symbols)

    def _composite_logic(
        self,
        preset: Preset,
        stage2: dict[str, dict[str, tuple[bool, float]]],
        symbols: list[str],
    ) -> dict[str, dict[str, Any]]:
        """Symbol passes if ANY group passes (groups are OR-ed together).

        Within each group, screeners are AND-ed (GroupLogic.AND) or OR-ed
        (GroupLogic.OR) according to the group's ``logic`` attribute.
        """
        combined: dict[str, dict[str, Any]] = {}
        for sym in symbols:
            matching_groups: list[str] = []
            for group in preset.groups:
                enabled_refs = [r for r in group.screeners if r.enabled]
                if not enabled_refs:
                    continue
                if group.logic == GroupLogic.AND:
                    group_pass = all(
                        stage2.get(r.screener_id, {}).get(sym, (False, 0.0))[0]
                        for r in enabled_refs
                    )
                else:  # OR
                    group_pass = any(
                        stage2.get(r.screener_id, {}).get(sym, (False, 0.0))[0]
                        for r in enabled_refs
                    )
                if group_pass:
                    matching_groups.append(group.group_id)

            passed = len(matching_groups) > 0
            score = len(matching_groups) / max(len(preset.groups), 1)
            combined[sym] = {
                "passed": passed,
                "score": score,
                "matching_groups": matching_groups,
            }
        return combined

    def _weighted_logic(
        self,
        preset: Preset,
        stage2: dict[str, dict[str, tuple[bool, float]]],
        symbols: list[str],
    ) -> dict[str, dict[str, Any]]:
        """Score = Σ(score_i × weight_i) / Σ(weights) for enabled screeners."""
        threshold = preset.threshold if preset.threshold is not None else 0.5
        enabled = [r for r in preset.screeners if r.enabled and r.weight is not None]
        total_weight = sum(float(r.weight) for r in enabled)  # type: ignore[arg-type]  # narrowed to non-None by list comprehension guard above

        combined: dict[str, dict[str, Any]] = {}
        for sym in symbols:
            if total_weight == 0.0:
                combined[sym] = {"passed": False, "score": 0.0}
                continue
            weighted_sum = sum(
                stage2.get(r.screener_id, {}).get(sym, (False, 0.0))[1]
                * float(r.weight)  # type: ignore[arg-type]  # narrowed to non-None by list comprehension guard above
                for r in enabled
            )
            score = weighted_sum / total_weight
            combined[sym] = {"passed": score >= threshold, "score": score}
        return combined

    # ------------------------------------------------------------------
    # Stage 3 — LLM ranking
    # ------------------------------------------------------------------

    def _run_stage3(
        self,
        preset: Preset,
        combined: dict[str, dict[str, Any]],
        bars: dict[str, list[Any]],
        market_caps: dict[str, float] | None = None,
    ) -> tuple[dict[str, dict[str, Any]], list[AITranscriptTurn]]:
        """Re-rank Stage 2 passing symbols with CloudAIScreener.

        Returns (merged_combined, ai_transcript). On any error falls back to
        Stage 2 results with an empty transcript and logs a WARNING.

        Input cap: the AI analyses at most ``_AI_MAX_INPUT`` stocks. When more
        pass Stage 2, only the top ``_AI_TOP_BY_CAP`` by market cap are sent;
        the rest are dropped from the passing set.
        """
        registry = self._get_registry()
        result = dict(combined)
        passing = [sym for sym, d in result.items() if d.get("passed", False)]
        if not passing:
            return result, []

        if len(passing) > _AI_MAX_INPUT:
            caps = market_caps or {}
            passing = sorted(
                passing, key=lambda s: caps.get(s, 0.0), reverse=True,
            )[:_AI_TOP_BY_CAP]
            kept = set(passing)
            for sym, d in result.items():
                if d.get("passed", False) and sym not in kept:
                    result[sym] = {**d, "passed": False}
            notice = (
                f"[Screener] Stage 3 does not support more than {_AI_MAX_INPUT} "
                f"stocks for analysis — showing the top {_AI_TOP_BY_CAP} by market cap"
            )
            _log.warning(notice)
            if self._notify is not None:
                self._notify("WARNING", notice)

        llm = registry.get("llm_claude_ranking")
        top_n: int = preset.top_n or len(passing)
        llm_config: dict[str, Any] = {
            "top_n":            top_n,
            "ai_query":         preset.ai_query,
            "ai_model":         preset.ai_model,
            "db":               self._db,
            "passing_symbols":  set(passing),
        }
        try:
            ranked = llm.apply(passing, bars, llm_config)
        except Exception as exc:
            _log.warning(
                "Stage 3 LLM error (%s) — falling back to Stage 2 results.",
                type(exc).__name__,
            )
            raw_transcript = getattr(llm, "last_transcript", None)
            partial: list[AITranscriptTurn] = (
                raw_transcript if isinstance(raw_transcript, list) else []
            )
            return result, partial

        # Capture side-channels (SRD-SCR-013.007, SRD-SCR-014.003).
        raw_reasoning = getattr(llm, "last_reasoning", None)
        reasoning: dict[str, str] = raw_reasoning if isinstance(raw_reasoning, dict) else {}
        raw_transcript = getattr(llm, "last_transcript", None)
        transcript: list[AITranscriptTurn] = (
            raw_transcript if isinstance(raw_transcript, list) else []
        )

        # Merge ranked scores back into result
        for sym, (passed, score) in ranked.items():
            if sym in result:
                result[sym] = {
                    **result[sym],
                    "score":        score,
                    "passed":       passed,
                    "ai_reasoning": reasoning.get(sym, ""),
                }
        # Keep only top-N passing symbols
        ranked_passing = sorted(
            [sym for sym, d in result.items() if d.get("passed", False)],
            key=lambda s: result[s]["score"],
            reverse=True,
        )[:top_n]
        for sym in list(result.keys()):
            if result[sym].get("passed", False) and sym not in ranked_passing:
                result[sym] = {**result[sym], "passed": False}
        return result, transcript

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_registry(self) -> ScreenerRegistry:
        return self._registry if self._registry is not None else ScreenerRegistry()

    def _get_storage(self) -> ScreenerResultsStorage:
        return self._storage if self._storage is not None else ScreenerResultsStorage()
