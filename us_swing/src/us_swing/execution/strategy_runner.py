"""
Module: MD-EXE-010.001.M01 — Strategy Runner
Parent SRD: SRD-EXE-010.001
"""
from __future__ import annotations

import enum
import logging
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from us_swing.analysis import indicators
from us_swing.data.models import OHLCVBar

log = logging.getLogger(__name__)

_INTRADAY_DB_PATH: Path = Path.home() / ".usswing" / "candles.db"
_POLL_INTERVAL_MS: int = 30_000
_TF_TABLE: dict[str, str] = {"3m": "price_3m", "15m": "price_15m"}


# ── Tokenizer ─────────────────────────────────────────────────────────────────

class _TokKind(enum.Enum):
    IDENT  = "IDENT"
    NUMBER = "NUMBER"
    COMMA  = "COMMA"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    OP     = "OP"
    AND    = "AND"
    OR     = "OR"


@dataclass(frozen=True)
class _Token:
    kind: _TokKind
    value: str


_TOKEN_RE = re.compile(
    r"(?P<OP>>=|<=|==|!=|>|<)"
    r"|(?P<NUMBER>-?\d+(?:\.\d+)?)"
    r"|(?P<IDENT>[A-Za-z_]\w*)"
    r"|(?P<COMMA>,)"
    r"|(?P<LPAREN>\()"
    r"|(?P<RPAREN>\))"
    r"|(?P<SKIP>[ \t]+)"
    r"|(?P<MISMATCH>.)"
)


def _tokenize(expr: str) -> list[_Token]:
    tokens: list[_Token] = []
    for mo in _TOKEN_RE.finditer(expr):
        kind_name = mo.lastgroup
        val = mo.group(kind_name)
        if kind_name in ("SKIP",):
            continue
        if kind_name == "MISMATCH":
            raise ValueError(f"Unexpected character {val!r} in expression")
        if kind_name == "IDENT":
            upper = val.upper()
            if upper == "AND":
                tokens.append(_Token(_TokKind.AND, upper))
                continue
            if upper == "OR":
                tokens.append(_Token(_TokKind.OR, upper))
                continue
            tokens.append(_Token(_TokKind.IDENT, val))
        else:
            tokens.append(_Token(_TokKind[kind_name], val))
    return tokens


# ── AST nodes ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _IndicatorNode:
    name: str
    timeframe: str
    period: int


@dataclass(frozen=True)
class _CompareNode:
    left: _IndicatorNode | float
    op: str
    right: _IndicatorNode | float


@dataclass(frozen=True)
class _LogicalNode:
    op: str
    clauses: tuple[_CompareNode, ...]


# ── Parser ────────────────────────────────────────────────────────────────────

class _Parser:
    """Minimal recursive-descent parser for indicator condition expressions.

    Grammar:
        expr    := clause ((AND | OR) clause)*
        clause  := operand OP operand
        operand := indicator | NUMBER
        indicator := IDENT LPAREN IDENT COMMA NUMBER RPAREN
    """

    def __init__(self, tokens: list[_Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    def _peek(self) -> _Token | None:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else None

    def _consume(self, kind: _TokKind) -> _Token:
        tok = self._peek()
        if tok is None or tok.kind != kind:
            raise ValueError(
                f"Expected {kind.value} but got {tok!r} at position {self._pos}"
            )
        self._pos += 1
        return tok

    def _parse_indicator(self) -> _IndicatorNode:
        name_tok = self._consume(_TokKind.IDENT)
        self._consume(_TokKind.LPAREN)
        tf_tok = self._consume(_TokKind.IDENT)
        self._consume(_TokKind.COMMA)
        period_tok = self._consume(_TokKind.NUMBER)
        self._consume(_TokKind.RPAREN)
        return _IndicatorNode(
            name=name_tok.value.upper(),
            timeframe=tf_tok.value,
            period=int(float(period_tok.value)),
        )

    def _parse_operand(self) -> _IndicatorNode | float:
        tok = self._peek()
        if tok is None:
            raise ValueError("Unexpected end of expression")
        if tok.kind == _TokKind.NUMBER:
            self._pos += 1
            return float(tok.value)
        if tok.kind == _TokKind.IDENT:
            return self._parse_indicator()
        raise ValueError(f"Unexpected token {tok!r}")

    def _parse_clause(self) -> _CompareNode:
        left = self._parse_operand()
        op_tok = self._consume(_TokKind.OP)
        right = self._parse_operand()
        return _CompareNode(left=left, op=op_tok.value, right=right)

    def parse(self) -> _LogicalNode:
        clauses: list[_CompareNode] = [self._parse_clause()]
        logical_op = "AND"
        while True:
            tok = self._peek()
            if tok is None:
                break
            if tok.kind == _TokKind.AND:
                logical_op = "AND"
                self._pos += 1
                clauses.append(self._parse_clause())
            elif tok.kind == _TokKind.OR:
                logical_op = "OR"
                self._pos += 1
                clauses.append(self._parse_clause())
            else:
                break
        return _LogicalNode(op=logical_op, clauses=tuple(clauses))


# ── Candle loading ────────────────────────────────────────────────────────────

def _load_bars(
    symbol: str,
    timeframe: str,
    db_path: Path,
    limit: int = 200,
) -> list[OHLCVBar]:
    if not db_path.exists():
        return []
    table = _TF_TABLE.get(timeframe)
    if table is None:
        log.warning("[Strategy] Unsupported timeframe %r — no candles loaded", timeframe)
        return []
    try:
        with sqlite3.connect(str(db_path)) as conn:
            cur = conn.execute(
                f"SELECT symbol, datetime, open, high, low, close, volume "
                f"FROM {table} WHERE symbol = ? ORDER BY datetime ASC LIMIT ?",
                (symbol, limit),
            )
            rows = cur.fetchall()
        return [
            OHLCVBar(
                symbol=r[0],
                datetime=r[1],
                open=float(r[2]),
                high=float(r[3]),
                low=float(r[4]),
                close=float(r[5]),
                volume=int(r[6]),
                timeframe=timeframe,
            )
            for r in rows
        ]
    except Exception:
        log.warning("[Strategy] Failed to load bars for %s (%s)", symbol, timeframe)
        return []


# ── Indicator dispatch ────────────────────────────────────────────────────────

def _compute_indicator(bars: list[OHLCVBar], node: _IndicatorNode) -> float:
    if not bars:
        return float("nan")
    name = node.name
    if name == "EMA":
        return indicators.ema_value(bars, node.period)
    if name == "RSI":
        return indicators.rsi(bars, node.period)
    if name == "ATR":
        return indicators.atr(bars, node.period)
    log.warning("[Strategy] Unknown indicator %r — treating as non-matching", name)
    return float("nan")


def _eval_op(lv: float, op: str, rv: float) -> bool:
    import math
    if math.isnan(lv) or math.isnan(rv):
        return False
    return {
        ">":  lv > rv,
        "<":  lv < rv,
        ">=": lv >= rv,
        "<=": lv <= rv,
        "==": lv == rv,
        "!=": lv != rv,
    }.get(op, False)


# ── ConditionEvaluator ────────────────────────────────────────────────────────

class ConditionEvaluator:
    """Parse and evaluate a free-form indicator expression for a single symbol."""

    def __init__(self, db_path: Path = _INTRADAY_DB_PATH) -> None:
        self._db_path = db_path

    def evaluate(self, symbol: str, expression: str) -> bool:
        if not expression.strip():
            return False
        try:
            return self._eval(symbol, expression)
        except Exception:
            log.warning(
                "[Strategy] Condition evaluation failed for %s — expr: %.120s",
                symbol, expression,
            )
            return False

    def _eval(self, symbol: str, expression: str) -> bool:
        tokens = _tokenize(expression)
        ast = _Parser(tokens).parse()

        # Collect unique (timeframe, period) pairs and load bars once per timeframe
        timeframes: set[str] = set()
        for clause in ast.clauses:
            for operand in (clause.left, clause.right):
                if isinstance(operand, _IndicatorNode):
                    timeframes.add(operand.timeframe)

        bar_cache: dict[str, list[OHLCVBar]] = {
            tf: _load_bars(symbol, tf, self._db_path)
            for tf in timeframes
        }

        results: list[bool] = []
        for clause in ast.clauses:
            lv = self._resolve(clause.left, bar_cache)
            rv = self._resolve(clause.right, bar_cache)
            results.append(_eval_op(lv, clause.op, rv))

        if ast.op == "OR":
            return any(results)
        return all(results)

    @staticmethod
    def _resolve(operand: _IndicatorNode | float, bar_cache: dict[str, list[OHLCVBar]]) -> float:
        if isinstance(operand, float):
            return operand
        bars = bar_cache.get(operand.timeframe, [])
        return _compute_indicator(bars, operand)


# ── Scope helper ─────────────────────────────────────────────────────────────

def _apply_scope(all_symbols: list[str], config: Any) -> list[str]:
    if config.symbol_mode == "include":
        inc: set[str] = set(config.symbols_include)
        return [s for s in all_symbols if s in inc]
    if config.symbol_mode == "exclude":
        exc: set[str] = set(config.symbols_exclude)
        return [s for s in all_symbols if s not in exc]
    return list(all_symbols)


# ── StrategyRunWorker ─────────────────────────────────────────────────────────

class StrategyRunWorker(QThread):
    """Background polling thread that drives the Active → Running → Active state machine."""

    status_changed = pyqtSignal(str, str)   # (strategy_name, new_status)
    symbols_changed = pyqtSignal(str, list) # (strategy_name, running_symbols)

    def __init__(
        self,
        config: Any,
        get_filtered_symbols: Callable[[], list[str]],
        db_path: Path = _INTRADAY_DB_PATH,
        poll_interval_ms: int = _POLL_INTERVAL_MS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._get_filtered_symbols = get_filtered_symbols
        self._db_path = db_path
        self._poll_interval_ms = poll_interval_ms
        self._state: str = "Active"
        self._running_symbols: list[str] = []

    def run(self) -> None:
        evaluator = ConditionEvaluator(self._db_path)
        self._evaluator = evaluator
        while not self.isInterruptionRequested():
            self._tick()
            self._sleep_interruptible(self._poll_interval_ms)

    def _tick(self) -> None:
        if self._state == "Active":
            self._check_entry()
        elif self._state == "Running":
            self._check_exit()

    def _check_entry(self) -> None:
        try:
            symbols = self._get_filtered_symbols()
        except Exception:
            log.warning("[Strategy] Failed to retrieve filtered symbols for %s", self._config.name)
            return

        entry_expr: str = self._config.entry_condition
        entered = [s for s in symbols if self._evaluator.evaluate(s, entry_expr)]
        if entered:
            self._running_symbols = entered
            self._state = "Running"
            self.status_changed.emit(self._config.name, "Running")
            self.symbols_changed.emit(self._config.name, list(entered))
            log.info(
                "[Strategy] %s entered Running — %d stock(s) matched entry",
                self._config.name, len(entered),
            )

    def _check_exit(self) -> None:
        exit_expr: str = self._config.exit_condition
        still_running = [
            s for s in self._running_symbols
            if not self._evaluator.evaluate(s, exit_expr)
        ]
        if len(still_running) < len(self._running_symbols):
            exited_count = len(self._running_symbols) - len(still_running)
            log.info(
                "[Strategy] %s — %d stock(s) exited position",
                self._config.name, exited_count,
            )
        self._running_symbols = still_running
        if not self._running_symbols:
            self._state = "Active"
            self.status_changed.emit(self._config.name, "Active")
            self.symbols_changed.emit(self._config.name, [])
            log.info("[Strategy] %s returned to Active — all positions exited", self._config.name)

    def _sleep_interruptible(self, ms: int) -> None:
        elapsed = 0
        while elapsed < ms and not self.isInterruptionRequested():
            QThread.msleep(100)
            elapsed += 100

    def request_stop(self) -> None:
        self.requestInterruption()
