# Functional Overview — Market Analytics (MKT)

**Document ID:** FO-MKT
**Version:** 0.1.0
**Status:** Draft
**Last Updated:** 2026-11-05
**Project:** US Swing Trading System

> v0.1.0: Tool created by architecture review. All FOs are outlines; each is filled in full at the start of its phase.

MKT finds S&P 500 stocks before they move, long or short, with a top-down funnel: regime → sectors → industry groups → relative strength → money flow → pre-breakout setups → AI review. It produces a Swing Readiness Score (0–100) and a ranked idea list. MKT runs inside the DSK desk process and writes to `desk.db`. Phases P1–P4 use no AI. Design source: https://claude.ai/artifact/4JJKX2kVZ9bvNkurFRuQkx.

---

## FO-MKT-001: Market Regime, Breadth and Fear

**Status:** Draft (outline)
**Priority:** Must
**Phase:** P1

- The system shall classify the daily market regime (trend and volatility) from SPY, index and VIX data.
- The system shall compute daily breadth for the S&P 500 (above 20/50/200-day MA, new highs/lows, advance/decline).
- The system shall compute a fear reading from VIX level, VIX term and breadth.

## FO-MKT-002: Sector Strength and Rotation

**Status:** Draft (outline)
**Priority:** Must
**Phase:** P2

- The system shall rank the 11 sectors and their industry groups by relative strength against SPY.
- The system shall place each sector in a rotation quadrant (Leading, Weakening, Lagging, Improving).
- The system shall rank every S&P 500 stock by relative strength.

## FO-MKT-003: Money Flow, Setups, Readiness Score and Ideas

**Status:** Draft (outline)
**Priority:** Must
**Phase:** P3

- The system shall measure money flow per stock (volume, accumulation and distribution).
- The system shall detect pre-breakout setups, long and short.
- The system shall score each stock 0–100 (RS 20, flow 20, setup 20, sector 15, regime 15, news 10) minus penalties.
- The system shall publish a ranked idea list with reasons and trigger prices.

## FO-MKT-004: Proof on Past Data

**Status:** Draft (outline)
**Priority:** Must
**Phase:** P4
**Depends on:** FO-BKT-002 (backtest engine)

- The system shall replay the score on past data and report hit rate and forward returns per score band.

## FO-MKT-005: AI Experts, Risk Manager and Trade Manager

**Status:** Draft (outline)
**Priority:** Must
**Phase:** P5a–P5b
**Depends on:** FO-DSK-002–005

- The system shall run ATLAS (regime), TIDE (sector and flow) and PIVOT (setup) as expert agents over the funnel output.
- The system shall let SENTINEL veto any idea that breaks hard risk limits kept in code.
- The system shall let HELM pick the final ideas and write a brief to the AI feed.

## FO-MKT-006: News and Global Events (SCOUT)

**Status:** Draft (outline)
**Priority:** Should
**Phase:** P5c

- The system shall collect news and calendar events and tag their impact on sectors and stocks.

## FO-MKT-007: AI Canvas Pages (CANVAS)

**Status:** Draft (outline)
**Priority:** Could
**Phase:** P5d

- The system shall let CANVAS write HTML/CSS pages shown in a sealed web view with no network access.

## FO-MKT-008: Link to Execution

**Status:** Draft (outline)
**Priority:** Should
**Phase:** P7
**Depends on:** open question — does HELM place trades or does the user approve each one

- The system shall send approved ideas to the Execution tool as watchlist entries or trade signals.
