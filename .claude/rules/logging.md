# Logging Rules

Applies to every log message written in `us_swing` — `_log.*`, `log.*`, `logging.*`.

## User-Facing Language

Log messages are read by the user in the GUI log panel, not just developers in a terminal.
Write every message as if it will appear in a product UI:

- **No class names, method names, or internal identifiers** in the message text.
  Bad: `IntradayCandleLoader: IBKR connect failed`
  Good: `[Candles] IBKR connection failed`

- **No snake_case or camelCase tokens** visible to the user.
  Bad: `_on_readiness_done: loader replaced`
  Good: `[Candles] Readiness check superseded by a newer batch — skipping`

- **No code-style punctuation** (`→`, `%d/%d symbols`, raw exception `repr()`).
  Prefer plain English: `12 of 15 stocks`, `connection timed out`.

- **Use a `[Topic]` prefix** on every message so users can scan quickly:
  `[Candles]`, `[Feed]`, `[Screener]`, `[Universe]`, `[Market Watch]`, `[Network]`, etc.
  Keep it consistent — same topic always uses the same prefix.

## Level Guidelines

| Level | Use when |
|-------|----------|
| `DEBUG` | Internal detail only devs care about (bar counts, page numbers, raw timestamps). Never shown in GUI log panel by default. |
| `INFO` | Normal milestones the user should know about — started, connected, complete, skipped. |
| `WARNING` | Something unexpected happened but the app recovered automatically. |
| `ERROR` | A feature failed and requires user attention or action. |
| `EXCEPTION` | Unhandled exception — always include a stack trace via `log.exception()`. |

## Format Rules

- One sentence per message. No trailing periods.
- Quantities: `%d stock(s)`, `%d of %d`, `last saved: %s` — enough context to be actionable.
- Dates/times: human-readable (`2026-05-06`), never raw epoch integers.
- Avoid `ignored`, `skipped`, `fallback` as standalone words — say what actually happened instead.

## Examples

```python
# Bad
log.info("IntradayCandleLoader: yfinance fallback — fetching %d symbol(s)", n)
log.warning("_ReadinessWorker: failed to check candle readiness")

# Good
log.info("[Candles] Downloading %d stock(s) via Yahoo Finance", n)
log.warning("[Candles] Failed to check readiness from local database")
```
