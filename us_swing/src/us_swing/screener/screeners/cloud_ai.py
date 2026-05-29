"""
Module: MD-SCR-002.003.M06 — screeners/cloud_ai.py
Parent SRD: SRD-SCR-002.005, SRD-SCR-013.005

Provider-agnostic Cloud AI ranking screener (Stage 3).

Backend: OpenRouter (https://openrouter.ai), an OpenAI-compatible gateway
that proxies 100+ models behind one API key.  When ``config['ai_query']``
is empty, a single-shot ranking prompt runs (legacy behaviour).  When
non-empty, a tool-augmented multi-turn agentic loop runs: the model can
call ``get_candle_data`` via ``CandleToolExecutor`` to inspect daily/weekly
OHLCV before scoring, and returns per-symbol reasoning (≤ 50 words)
alongside scores.

The API key is loaded from the OS keychain at call time — never read from
``config`` and never serialised to disk.
"""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Final, NamedTuple, Protocol

try:
    import openai
    from openai import APIStatusError, RateLimitError
except ImportError:  # pragma: no cover
    openai = None  # type: ignore[assignment]  # optional dep; guarded by `if openai is None` checks
    APIStatusError = Exception  # type: ignore[misc,assignment]  # sentinel for except clause
    RateLimitError = Exception  # type: ignore[misc,assignment]  # sentinel for except clause

from us_swing.screener.screeners import _api_key_store
from us_swing.screener.screeners._cloud_ai_models import (
    DEFAULT_MODEL,
    OPENROUTER_BASE,
)
from us_swing.screener.screeners._tool_executor import (
    TOOL_NAME as CANDLE_TOOL_NAME,
    CandleToolExecutor,
)
from us_swing.data.models import OHLCVBar
from us_swing.screener.storage import AITranscriptTurn

_log = logging.getLogger(__name__)

_COST_THRESHOLD_USD: Final[float] = 50.0
_REASONING_MAX_WORDS: Final[int] = 50
_AGENTIC_MAX_TURNS: Final[int] = 8
_REQUEST_TIMEOUT_S: Final[float] = 60.0
_RETRY_DELAYS_S: Final[tuple[float, ...]] = (1.0, 3.0, 7.0)
_RETRY_STATUSES: Final[frozenset[int]] = frozenset({429, 502, 503, 504})

_RSLP_ENC: Final[dict[str, str]] = {"rising": "R", "falling": "F", "flat": "="}
_VOL_ENC: Final[dict[str, str]] = {"expanding": "EXP", "contracting": "CON", "neutral": "NEU"}

# Feature-extraction tuning
_DAILY_6M: Final[int] = 126  # ~6 months of trading days
_WEEKLY_6M: Final[int] = 26  # ~6 months of weekly bars
_SWING_N: Final[int] = 5  # pivot neighbours on each side (5 = proper swing structure)
_SWING_MAX: Final[int] = 10  # most-recent swing points sent to AI
_SWING_ATR_MULT: Final[float] = 1.0  # min move between same-direction pivots (× ATR); filters chop

_GET_CANDLE_DATA_TOOL: Final[dict[str, Any]] = {
    "type": "function",
    "function": {
        "name": CANDLE_TOOL_NAME,
        "description": (
            "Fetch historical OHLCV candle data for a symbol that passed Stage-2 "
            "screening.  Use this to examine price action, compute patterns, or "
            "assess momentum before scoring.  Limited to 3 calls per symbol."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "symbol":        {"type": "string"},
                "timeframe":     {"type": "string", "enum": ["1d", "1w"]},
                "lookback_bars": {"type": "integer", "minimum": 1, "maximum": 300},
            },
            "required": ["symbol", "timeframe", "lookback_bars"],
        },
    },
}


# ---------------------------------------------------------------------------
# Feature extraction helpers
# ---------------------------------------------------------------------------

class _BarProto(Protocol):
    """Structural type accepted by feature helpers that work on both OHLCVBar and _WkBar."""
    datetime: datetime
    high: float
    low: float


class _WkBar(NamedTuple):
    """Minimal weekly bar used only inside feature extraction."""
    datetime: datetime
    high: float
    low: float


def _compute_rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(len(closes) - period, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_g = sum(gains) / period
    avg_l = sum(losses) / period
    if avg_g == 0.0 and avg_l == 0.0:
        return 50.0
    if avg_l == 0.0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + avg_g / avg_l)


def _compute_atr(bars: list[_BarProto], period: int = 14) -> float:
    trs = [b.high - b.low for b in bars[max(0, len(bars) - period):]]
    return sum(trs) / len(trs) if trs else 0.0


def _to_weekly(bars: list[OHLCVBar]) -> list[_WkBar]:
    """Aggregate daily bars into weekly bars keyed by ISO year-week."""
    buckets: dict[tuple[int, int], list[OHLCVBar]] = defaultdict(list)
    for b in bars:
        iso = b.datetime.isocalendar()
        buckets[(iso[0], iso[1])].append(b)
    result: list[_WkBar] = []
    for key in sorted(buckets):
        week = sorted(buckets[key], key=lambda x: x.datetime)
        result.append(_WkBar(
            datetime=week[0].datetime,
            high=max(b.high for b in week),
            low=min(b.low  for b in week),
        ))
    return result


def _find_swings(
    bars: list[_BarProto],
    *,
    use_high:   bool,
    neighbors:  int   = _SWING_N,
    max_pts:    int   = _SWING_MAX,
    atr_filter: float = 0.0,
) -> list[dict[str, Any]]:
    """Return the ``max_pts`` most-recent swing pivot points.

    ``atr_filter``: when > 0, a candidate pivot is only accepted when its
    price differs from the last accepted pivot by at least this value
    (pass ``ATR × _SWING_ATR_MULT``).  Consecutive same-direction pivots
    closer than one ATR indicate a choppy, range-bound market and are skipped.
    """
    pts: list[dict[str, Any]] = []
    last_accepted: float | None = None
    n = len(bars)
    for i in range(neighbors, n - neighbors):
        val   = bars[i].high if use_high else bars[i].low
        left  = [bars[j].high if use_high else bars[j].low for j in range(i - neighbors, i)]
        right = [bars[j].high if use_high else bars[j].low for j in range(i + 1, i + neighbors + 1)]
        is_pivot = (
            (    use_high and all(val > v for v in left + right)) or
            (not use_high and all(val < v for v in left + right))
        )
        if not is_pivot:
            continue
        if atr_filter > 0 and last_accepted is not None:
            if abs(val - last_accepted) < atr_filter:
                continue          # too close to previous pivot — choppy noise
        pts.append({"date": bars[i].datetime.strftime("%Y-%m-%d"), "price": round(val, 2)})
        last_accepted = val
    return pts[-max_pts:]


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def _extract_features(sym: str, bars: list[OHLCVBar]) -> dict[str, Any]:
    closes = [b.close for b in bars]
    n = len(closes)
    price = closes[-1]

    # Trend: direction over entire bar window
    trend = "up" if price > closes[0] else "down"

    # Momentum: % change over last 20 bars
    mom_20d = round((price / closes[-21] - 1) * 100, 1) if n >= 21 else 0.0

    # RSI + slope
    rsi = _compute_rsi(closes)
    rsi_prev = _compute_rsi(closes[:-5]) if n > 20 else rsi
    rsi_slope = "rising" if rsi > rsi_prev + 1 else ("falling" if rsi < rsi_prev - 1 else "flat")

    # ATR
    atr = round(_compute_atr(bars), 2)

    # Moving averages
    def _ma(p: int) -> float:
        return round(sum(closes[-p:]) / min(n, p), 2)

    ma20, ma50, ma200 = _ma(20), _ma(50), _ma(200)

    # Volume trend: 10-bar avg vs 30-bar avg
    vol10 = sum(b.volume for b in bars[-10:]) / min(n, 10)
    vol30 = sum(b.volume for b in bars[-30:]) / min(n, 30)
    vol_trend = (
        "expanding"   if vol10 > vol30 * 1.1 else
        "contracting" if vol10 < vol30 * 0.9 else
        "neutral"
    )

    # 52-week high/low
    yr = bars[-252:] if n >= 252 else bars
    high_52w = round(max(b.high for b in yr), 2)
    low_52w  = round(min(b.low  for b in yr), 2)
    pct_off_high = round((price - high_52w) / high_52w * 100, 1)

    # Daily swing pivots — last 6 months (~126 bars), ATR-filtered
    d6m        = bars[-_DAILY_6M:] if n >= _DAILY_6M else bars
    daily_atr  = _compute_atr(d6m)
    atr_daily  = daily_atr * _SWING_ATR_MULT
    sh_1d = _find_swings(d6m, use_high=True,  atr_filter=atr_daily)
    sl_1d = _find_swings(d6m, use_high=False, atr_filter=atr_daily)

    # Weekly swing pivots — last 6 months (~26 weeks), ATR-filtered
    weekly     = _to_weekly(bars)
    w6m        = weekly[-_WEEKLY_6M:] if len(weekly) >= _WEEKLY_6M else weekly
    weekly_atr = _compute_atr(w6m) * _SWING_ATR_MULT
    sh_1w = _find_swings(w6m, use_high=True,  atr_filter=weekly_atr)
    sl_1w = _find_swings(w6m, use_high=False, atr_filter=weekly_atr)

    return {
        "price":             round(price, 2),
        "trend":             trend,
        "momentum_20d_pct":  mom_20d,
        "rsi_14":            round(rsi, 1),
        "rsi_slope":         rsi_slope,
        "atr_14":            atr,
        "ma20":              ma20,
        "ma50":              ma50,
        "ma200":             ma200,
        "above_ma20":        price > ma20,
        "above_ma50":        price > ma50,
        "above_ma200":       price > ma200,
        "volume_trend":      vol_trend,
        "high_52w":          high_52w,
        "low_52w":           low_52w,
        "pct_off_52w_high":  pct_off_high,
        "swing_highs_1d":    sh_1d,
        "swing_lows_1d":     sl_1d,
        "swing_highs_1w":    sh_1w,
        "swing_lows_1w":     sl_1w,
    }


# ---------------------------------------------------------------------------
# Compact serialiser
# ---------------------------------------------------------------------------

def _features_to_table(features: dict[str, dict[str, Any]]) -> str:
    """Serialise batch_features output as a compact table + swing-pivot block.

    ~82% fewer tokens than json.dumps(features, indent=2) for a 20-symbol batch.
    """
    _HDR = (
        "=== FEATURES "
        "(SYM|PRICE|TREND|MOM20%|RSI|RSLP|ATR|MA20|MA50|MA200|MAFLG|VOL|H52W|L52W|OFF52%) ===\n"
        "Legend: TREND=U/D  RSLP=R(rising)/F(falling)/=(flat)  "
        "MAFLG=above_MA20/50/200 as Y/N  VOL=EXP/CON/NEU"
    )
    _PHDR = (
        "=== SWING PIVOTS "
        "(dH/dL=daily high/low, wH/wL=weekly; price@MMDD oldest→newest) ==="
    )
    scalar_lines: list[str] = [_HDR]
    pivot_lines: list[str] = [_PHDR]

    for sym, feat in features.items():
        maflg = (
            ("Y" if feat["above_ma20"] else "N")
            + ("Y" if feat["above_ma50"] else "N")
            + ("Y" if feat["above_ma200"] else "N")
        )
        scalar_lines.append("|".join([
            sym,
            f"{feat['price']:.2f}",
            "U" if feat["trend"] == "up" else "D",
            f"{feat['momentum_20d_pct']:+.1f}",
            f"{feat['rsi_14']:.1f}",
            _RSLP_ENC.get(feat["rsi_slope"], feat["rsi_slope"]),
            f"{feat['atr_14']:.2f}",
            f"{feat['ma20']:.2f}",
            f"{feat['ma50']:.2f}",
            f"{feat['ma200']:.2f}",
            maflg,
            _VOL_ENC.get(feat["volume_trend"], feat["volume_trend"]),
            f"{feat['high_52w']:.2f}",
            f"{feat['low_52w']:.2f}",
            f"{feat['pct_off_52w_high']:+.1f}",
        ]))

        parts: list[str] = [sym]
        for prefix, key in (
            ("dH", "swing_highs_1d"),
            ("dL", "swing_lows_1d"),
            ("wH", "swing_highs_1w"),
            ("wL", "swing_lows_1w"),
        ):
            pivots: list[dict[str, Any]] = feat.get(key, [])
            if pivots:
                encoded = ",".join(
                    f"{p['price']:g}@{p['date'][5:7]}{p['date'][8:]}"
                    for p in pivots
                )
                parts.append(f"{prefix}:{encoded}")
        pivot_lines.append(" ".join(parts))

    return "\n".join(scalar_lines) + "\n\n" + "\n".join(pivot_lines)


# ---------------------------------------------------------------------------
# Screener
# ---------------------------------------------------------------------------

class _UsageTracker(Protocol):
    """Duck-typed interface for API usage tracking."""
    def log_usage(self, *, tokens_in: int, tokens_out: int) -> None: ...
    def get_monthly_cost(self) -> float: ...


class CloudAIScreener:
    """MD-SCR-002.003.M06 — Cloud AI ranking screener (Stage 3 only).

    ``batch_features()`` extracts indicator features without any API call.
    ``apply()`` selects between two paths based on ``config['ai_query']``:

    * **Legacy path** (empty query):  single-shot ranking call, no tools.
    * **Tool-augmented path** (non-empty query):  multi-turn ``tool_calls``
      loop; the model may call ``get_candle_data`` via
      ``CandleToolExecutor``; returns per-symbol reasoning in
      ``self.last_reasoning``.

    On any API or parsing error, both paths fall back to ``(passed=True,
    score=0.0)`` for every symbol so the pipeline can complete.
    """

    def __init__(self, usage_tracker: _UsageTracker | None = None) -> None:
        self._usage_tracker = usage_tracker
        self.last_reasoning: dict[str, str] = {}
        self.last_transcript: list[AITranscriptTurn] = []

    def batch_features(
        self,
        symbols: list[str],
        bars: dict[str, list[OHLCVBar]],
    ) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for sym in symbols:
            sym_bars = bars.get(sym, [])
            if sym_bars:
                result[sym] = _extract_features(sym, sym_bars)
        return result

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def apply(
        self,
        symbols: list[str],
        bars: dict[str, list[OHLCVBar]],
        config: dict[str, Any],
    ) -> dict[str, tuple[bool, float]]:
        self.last_reasoning = {}
        self.last_transcript = []
        ai_query = str(config.get("ai_query", "")).strip()
        if ai_query:
            return self._apply_with_tools(symbols, bars, config, ai_query)
        return self._apply_legacy(symbols, bars, config)

    # ------------------------------------------------------------------
    # Client + retry helpers
    # ------------------------------------------------------------------

    def _make_client(self) -> Any:  # Any: openai.OpenAI — type unavailable when dep is absent
        if openai is None:
            raise RuntimeError("openai package not installed")
        key = _api_key_store.load()
        if not key:
            raise RuntimeError(
                "No OpenRouter API key configured. "
                "Add your key in Settings → AI Models."
            )
        return openai.OpenAI(
            base_url=OPENROUTER_BASE,
            api_key=key,
            default_headers={
                "HTTP-Referer": "https://github.com/usswing",
                "X-Title":      "USSwing Screener",
            },
            timeout=_REQUEST_TIMEOUT_S,
        )

    def _call_with_retry(self, client: Any, **kwargs: Any) -> Any:
        """Bounded exponential backoff for transient errors (429/5xx)."""
        last_exc: Exception | None = None
        all_delays = (0.0, *_RETRY_DELAYS_S)
        for attempt, delay in enumerate(all_delays):
            if delay:
                time.sleep(delay)  # Safe: always called from ThreadPoolExecutor, not the asyncio event loop
            try:
                return client.chat.completions.create(**kwargs)
            except (RateLimitError, APIStatusError) as exc:
                status = getattr(exc, "status_code", None)
                if status not in _RETRY_STATUSES:
                    raise
                last_exc = exc
                is_last = attempt == len(_RETRY_DELAYS_S)
                next_delay = all_delays[attempt + 1] if not is_last else 0.0
                _log.warning(
                    "CloudAI: HTTP %s on attempt %d — %s.",
                    status, attempt + 1,
                    "giving up" if is_last else f"retrying after {next_delay:.1f}s",
                )
        assert last_exc is not None
        raise last_exc

    # ------------------------------------------------------------------
    # Legacy single-shot path
    # ------------------------------------------------------------------

    def _apply_legacy(
        self,
        symbols: list[str],
        bars: dict[str, list[OHLCVBar]],
        config: dict[str, Any],
    ) -> dict[str, tuple[bool, float]]:
        model = str(config.get("ai_model", DEFAULT_MODEL))
        features = self.batch_features(symbols, bars)
        features_text = _features_to_table(features)
        prompt = (
            f"You are a swing-trade analyst. Rank the following symbols by "
            f"swing-trade suitability using the pre-extracted features below.\n\n"
            f"Symbols: {', '.join(symbols)}\n\nFeatures:\n{features_text}\n\n"
            f"Respond with ONLY a raw JSON object — no explanation, no markdown, "
            f"no prose. Format: {{\"SYMBOL\": 0.0, ...}} where each value is a "
            f"score in [0.0, 1.0]. Example: {{\"AAPL\": 0.82, \"MSFT\": 0.61}}"
        )
        fallback = {sym: (True, 0.0) for sym in symbols}
        t_sent = datetime.now(timezone.utc)
        sent_iso = t_sent.strftime("%Y-%m-%dT%H:%M:%SZ")
        _user_summary = f"Analysing technical data for: {', '.join(symbols)}"
        self.last_transcript = [
            AITranscriptTurn(role="user", content=_user_summary, sent_at=sent_iso),
        ]

        try:
            client = self._make_client()
        except Exception as exc:
            _log.warning("CloudAIScreener: client init failed (%s) — fallback.", type(exc).__name__)
            self.last_transcript.append(AITranscriptTurn(
                role="system",
                content=f"AI ranking unavailable: client init failed ({type(exc).__name__}). "
                        f"Falling back to Stage 2 results.",
            ))
            return fallback

        t0_ns = time.monotonic_ns()
        try:
            response = self._call_with_retry(
                client,
                model=model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            _log.warning(
                "CloudAIScreener: API error (%s) — fallback to pass-all.",
                type(exc).__name__,
            )
            self.last_transcript.append(AITranscriptTurn(
                role="system",
                content=f"AI ranking unavailable: API error ({type(exc).__name__}). "
                        f"Falling back to Stage 2 results.",
            ))
            return fallback
        t_recv = datetime.now(timezone.utc)
        # Includes retry backoff sleep on 429s; reflects wall-clock wait, not pure server latency.
        elapsed_ms = int((time.monotonic_ns() - t0_ns) / 1_000_000)

        self._track_usage(response)

        recv_iso = t_recv.strftime("%Y-%m-%dT%H:%M:%SZ")
        usage = getattr(response, "usage", None)
        try:
            raw_text = response.choices[0].message.content or ""
        except (IndexError, AttributeError):
            _log.warning("CloudAIScreener: could not read response content — fallback.")
            self.last_transcript.append(AITranscriptTurn(
                role="assistant", content="",
                received_at=recv_iso, response_time_ms=elapsed_ms,
            ))
            self.last_transcript.append(AITranscriptTurn(
                role="system",
                content="AI ranking unavailable: response had no readable content. "
                        "Falling back to Stage 2 results.",
            ))
            return fallback
        _log.debug("CloudAIScreener: raw response text: %r", raw_text)
        self.last_transcript.append(AITranscriptTurn(
            role="assistant",
            content=_strip_codefence(raw_text),
            tokens_input=getattr(usage, "prompt_tokens", 0) if usage else 0,
            tokens_output=getattr(usage, "completion_tokens", 0) if usage else 0,
            received_at=recv_iso,
            response_time_ms=elapsed_ms,
        ))
        try:
            raw_scores = json.loads(_strip_codefence(raw_text))
        except json.JSONDecodeError:
            _log.warning(
                "CloudAIScreener: could not parse response JSON — raw text: %r", raw_text,
            )
            self.last_transcript.append(AITranscriptTurn(
                role="system",
                content="AI ranking unavailable: response was not valid JSON. "
                        "Falling back to Stage 2 results.",
            ))
            return fallback

        return _scores_to_results(symbols, raw_scores)

    # ------------------------------------------------------------------
    # Tool-augmented multi-turn path
    # ------------------------------------------------------------------

    def _apply_with_tools(
        self,
        symbols: list[str],
        bars: dict[str, list[OHLCVBar]],
        config: dict[str, Any],
        ai_query: str,
    ) -> dict[str, tuple[bool, float]]:
        model = str(config.get("ai_model", DEFAULT_MODEL))
        db = config.get("db")
        passing_symbols: set[str] = set(config.get("passing_symbols", symbols))

        if db is None:
            _log.warning(
                "CloudAIScreener: ai_query set but no 'db' in config — "
                "tool calls disabled, falling back to legacy path."
            )
            return self._apply_legacy(symbols, bars, config)

        features = self.batch_features(symbols, bars)
        tool_executor = CandleToolExecutor(db, passing_symbols)

        system_prompt = (
            "You are a swing-trade analyst.  Rank the supplied stocks "
            f"according to the user's query: {ai_query!r}.\n\n"
            "Use the get_candle_data tool to inspect daily or weekly bars "
            "when the pre-extracted features are insufficient.  When ready, "
            "respond with ONLY a JSON array (no prose) of the form:\n"
            '[{"symbol": "TICK", "score": 0.0..1.0, '
            '"reasoning": "≤ 50 words"}, ...]'
        )
        user_msg = (
            f"Symbols passing Stage 2: {', '.join(symbols)}\n\n"
            f"Pre-extracted features:\n{_features_to_table(features)}"
        )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_msg},
        ]
        t_user = datetime.now(timezone.utc)
        transcript: list[AITranscriptTurn] = [
            AITranscriptTurn(role="system", content=system_prompt),
            AITranscriptTurn(
                role="user",
                content=f"Analysing technical data for: {', '.join(symbols)}",
                sent_at=t_user.strftime("%Y-%m-%dT%H:%M:%SZ"),
            ),
        ]
        self.last_transcript = transcript
        fallback = {sym: (True, 0.0) for sym in symbols}

        try:
            client = self._make_client()
        except Exception as exc:
            _log.warning("CloudAIScreener: client init failed (%s) — fallback.",
                         type(exc).__name__)
            transcript.append(AITranscriptTurn(
                role="system",
                content=f"AI ranking unavailable: client init failed ({type(exc).__name__}). "
                        f"Falling back to Stage 2 results.",
            ))
            return fallback

        final_text = ""
        for turn in range(_AGENTIC_MAX_TURNS):
            t_sent = datetime.now(timezone.utc)
            t0_ns = time.monotonic_ns()
            try:
                response = self._call_with_retry(
                    client,
                    model=model,
                    max_tokens=2048,
                    tools=[_GET_CANDLE_DATA_TOOL],
                    messages=messages,
                )
            except Exception as exc:
                _log.warning(
                    "CloudAIScreener: API error (%s) on turn %d — fallback.",
                    type(exc).__name__, turn,
                )
                transcript.append(AITranscriptTurn(
                    role="system",
                    content=f"AI ranking unavailable: API error ({type(exc).__name__}) "
                            f"on turn {turn + 1}. Falling back to Stage 2 results.",
                ))
                return fallback
            t_recv = datetime.now(timezone.utc)
            # Includes retry backoff sleep on 429s; reflects wall-clock wait, not pure server latency.
            elapsed_ms = int((time.monotonic_ns() - t0_ns) / 1_000_000)
            sent_iso = t_sent.strftime("%Y-%m-%dT%H:%M:%SZ")
            recv_iso = t_recv.strftime("%Y-%m-%dT%H:%M:%SZ")

            self._track_usage(response)
            usage = getattr(response, "usage", None)
            tok_in  = getattr(usage, "prompt_tokens",     0) if usage else 0
            tok_out = getattr(usage, "completion_tokens", 0) if usage else 0

            choice = response.choices[0]
            if choice.finish_reason == "tool_calls":
                tool_results = self._append_tool_round(messages, choice, tool_executor)
                # One assistant turn carries the token cost for this API call;
                # tool_result turns carry zero tokens to avoid double-counting.
                transcript.append(AITranscriptTurn(
                    role="assistant",
                    content=f"[{len(tool_results)} tool_call(s)]",
                    tokens_input=tok_in,
                    tokens_output=tok_out,
                    sent_at=sent_iso,
                    received_at=recv_iso,
                    response_time_ms=elapsed_ms,
                ))
                for tool_name, display, _inp in tool_results:
                    transcript.append(AITranscriptTurn(
                        role="tool_result",
                        content=display,
                        tool_name=tool_name,
                    ))
                continue

            final_text = choice.message.content or ""
            transcript.append(AITranscriptTurn(
                role="assistant",
                content=_strip_codefence(final_text),
                tokens_input=tok_in,
                tokens_output=tok_out,
                sent_at=sent_iso,
                received_at=recv_iso,
                response_time_ms=elapsed_ms,
            ))
            break
        else:
            _log.warning("CloudAIScreener: agentic loop exceeded %d turns — fallback.",
                         _AGENTIC_MAX_TURNS)
            transcript.append(AITranscriptTurn(
                role="system",
                content=f"AI ranking unavailable: agentic loop exceeded "
                        f"{_AGENTIC_MAX_TURNS} turns without a final answer. "
                        f"Falling back to Stage 2 results.",
            ))
            return fallback

        return self._parse_ranking(final_text, symbols, fallback)

    # ------------------------------------------------------------------
    # Tool-call round helper
    # ------------------------------------------------------------------

    @staticmethod
    def _tool_display(tool_name: str, tool_input: dict[str, Any]) -> str:
        if tool_name == CANDLE_TOOL_NAME:
            symbol = tool_input.get("symbol", "?")
            tf_raw = tool_input.get("timeframe", "")
            tf = "weekly" if tf_raw == "1w" else "daily"
            bars = tool_input.get("lookback_bars", "")
            bars_part = f", {bars} bars" if bars else ""
            return f"Fetched candle data for {symbol} ({tf}{bars_part}) for technical analysis"
        return f"Called {tool_name}"

    def _append_tool_round(
        self,
        messages: list[dict[str, Any]],
        choice: Any,
        tool_executor: CandleToolExecutor,
    ) -> list[tuple[str, str, dict[str, Any]]]:
        """Append the assistant's tool-call message + each tool's result.

        Returns list of (tool_name, display_text, tool_input) for transcript capture.
        """
        msg = choice.message
        tool_calls = msg.tool_calls or []
        messages.append({
            "role":       "assistant",
            "content":    msg.content or "",
            "tool_calls": [tc.model_dump() for tc in tool_calls],
        })
        results: list[tuple[str, str, dict[str, Any]]] = []
        for tc in tool_calls:
            try:
                tool_input = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                tool_input = {}
            output = tool_executor.execute(tc.function.name, tool_input)
            messages.append({
                "role":         "tool",
                "tool_call_id": tc.id,
                "content":      output,
            })
            display = self._tool_display(tc.function.name, tool_input)
            results.append((tc.function.name, display, tool_input))
        return results

    # ------------------------------------------------------------------
    # Parsing + usage tracking
    # ------------------------------------------------------------------

    def _parse_ranking(
        self,
        text: str,
        symbols: list[str],
        fallback: dict[str, tuple[bool, float]],
    ) -> dict[str, tuple[bool, float]]:
        try:
            raw = json.loads(_strip_codefence(text))
        except json.JSONDecodeError:
            _log.warning("CloudAIScreener: ranking JSON parse failed — fallback.")
            return fallback

        scores: dict[str, float] = {}
        for entry in raw if isinstance(raw, list) else []:
            sym = str(entry.get("symbol", "")).upper()
            if not sym:
                continue
            try:
                scores[sym] = float(entry.get("score", 0.0))
            except (TypeError, ValueError):
                scores[sym] = 0.0
            reasoning = str(entry.get("reasoning", "")).strip()
            self.last_reasoning[sym] = _truncate_words(reasoning, _REASONING_MAX_WORDS)

        if not scores:
            _log.warning("CloudAIScreener: ranking JSON was empty — fallback.")
            return fallback
        return _scores_to_results(symbols, scores)

    def _track_usage(self, response: Any) -> None:
        if self._usage_tracker is None:
            return
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        try:
            self._usage_tracker.log_usage(
                tokens_in=usage.prompt_tokens,
                tokens_out=usage.completion_tokens,
            )
        except AttributeError:
            return
        try:
            monthly = float(self._usage_tracker.get_monthly_cost())
        except (TypeError, ValueError):
            return
        if monthly > _COST_THRESHOLD_USD:
            _log.warning(
                "CloudAIScreener: monthly cost $%.2f exceeds $%.0f threshold.",
                monthly, _COST_THRESHOLD_USD,
            )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _scores_to_results(
    symbols: list[str], raw_scores: dict[str, float],
) -> dict[str, tuple[bool, float]]:
    out: dict[str, tuple[bool, float]] = {}
    for sym in symbols:
        try:
            raw_score = float(raw_scores.get(sym, 0.0))
        except (TypeError, ValueError):
            raw_score = 0.0
        out[sym] = (True, max(0.0, min(1.0, raw_score)))
    return out


def _strip_codefence(text: str) -> str:
    """Strip ``` fences and any leading prose before the JSON value.

    Handles three model output patterns:
      - Clean JSON (most common)
      - JSON wrapped in ```...``` code fences
      - Prefixed text like ":thought: ..." or a chain-of-thought preamble
        followed by the JSON array/object
    """
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1] if "\n" in s else s[3:]
        if s.endswith("```"):
            s = s[:-3]
    s = s.strip()
    # Slice off any leading prose before the opening [ or {
    for i, ch in enumerate(s):
        if ch in ("{", "["):
            return s[i:]
    return s


def _truncate_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])
