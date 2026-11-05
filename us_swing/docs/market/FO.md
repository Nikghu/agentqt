# Functional Overview — Market Analytics (MKT)

**Document ID:** FO-MKT
**Version:** 0.3.0
**Status:** Draft
**Last Updated:** 2026-11-05
**Project:** US Swing Trading System

> v0.4.0: FO-MKT-003 written in full as Draft (news points rescaled until P5c; earnings from Yahoo for top names; shorts gated by regime; top 10 per side at 60+).
> v0.3.0: FO-MKT-002 written in full as Draft (sector lines from member candles; industry groups later).
> v0.2.0: FO-MKT-001 written in full and approved (user, 2026-11-06).
> v0.1.0: Tool created by architecture review. All FOs are outlines; each is filled in full at the start of its phase.

MKT finds S&P 500 stocks before they move, long or short, with a top-down funnel: regime → sectors → industry groups → relative strength → money flow → pre-breakout setups → AI review. It produces a Swing Readiness Score (0–100) and a ranked idea list. MKT runs inside the DSK desk process and writes to `desk.db`. Phases P1–P4 use no AI. Design source: https://claude.ai/artifact/4JJKX2kVZ9bvNkurFRuQkx.

---

## FO-MKT-001: Market Regime, Breadth and Fear

**Status:** Approved (user, 2026-11-06: draft approved, VIX from Yahoo Finance, option A)
**Priority:** Must
**Phase:** P1
**Depends on:** FO-DSK-001 (desk process), FO-GUI-034 (Market Floor panels), daily candles in `candles.db`

The system shall describe the state of the whole US market each day, so later phases can judge every stock idea against it. No AI is used.

- The system shall classify each day's market regime from SPY as Uptrend, Downtrend or Choppy.
- The system shall classify market volatility as Calm, Normal or High from SPY's recent price swings compared with the past year.
- The system shall compute daily breadth for S&P 500 stocks: share above their 20, 50 and 200-day averages, 52-week new highs and lows, and advancing against declining stocks.
- The system shall give a daily fear reading (Calm, Nervous, Fearful) from volatility, breadth and VIX, using daily VIX and VIX3M from Yahoo Finance.
- The system shall run this as a desk step in the evening run and keep the results in `desk.db`.
- The system shall fill the whole available history on its first run, then add only new days.
- The system shall show the real regime and breadth on the Market Floor in place of sample data.

### Acceptance Criteria

1. For 3 chosen dates the regime, volatility and breadth match a hand check on the same candles.
2. With the app closed, the evening run adds the latest day and the Floor shows it after the app opens.
3. When Yahoo Finance is not reachable, the day is still stored and the fear reading says it was made without VIX.
4. The Market regime and Breadth panels show the data date and no "Sample data" tag.

## FO-MKT-002: Sector Strength and Rotation

**Status:** Approved (user, 2026-11-06)
**Priority:** Must
**Phase:** P2
**Depends on:** FO-MKT-001 (desk step and member candles), saved S&P 500 list with sectors

The system shall show which of the 11 sectors money is moving into or out of, and which stocks are the strongest, so later phases can favour strong stocks in strong sectors. No AI is used. Industry groups come later.

- The system shall build a daily strength line for each sector from the equal-weight daily moves of its member stocks.
- The system shall rank the sectors by their performance against SPY over 1, 3 and 6 months.
- The system shall place each sector in a rotation quadrant: Leading, Weakening, Lagging or Improving.
- The system shall give every member stock a relative strength rating from 1 to 99 and its rank inside its sector.
- The system shall run this as a desk step after the market regime step and keep the results in `desk.db`.
- The system shall show the real sector strength, sector rotation and the strongest stocks on the Market Floor.

### Acceptance Criteria

1. For 2 chosen dates the sector ranks, quadrants and three stock ratings match a hand check on the same candles.
2. The evening run adds the latest day for sectors and stock ratings.
3. The Sector strength, Sector rotation and RS leaders panels show real data with the data date and no "Sample data" tag.

## FO-MKT-003: Money Flow, Setups, Readiness Score and Ideas

**Status:** Draft
**Priority:** Must
**Phase:** P3
**Depends on:** FO-MKT-001 (regime), FO-MKT-002 (sectors and stock RS), daily candles with volume in `candles.db`

The system shall turn the regime, sector and RS results into a short daily list of long and short stock ideas, each with a trigger, a stop and its reasons, before the move starts. No AI is used. News joins the score in P5c.

- The system shall measure money flow for each stock from price and volume: accumulation and distribution days, Chaikin money flow and up against down volume.
- The system shall detect pre-breakout setups for longs (squeeze, flat base, pullback) and shorts (failed breakout, lower highs, breakdown), each with a trigger price and a stop.
- The system shall give each stock a Swing Readiness Score from 0 to 100 for long and for short, from RS, money flow, setup, sector and regime, minus penalties.
- The system shall leave out stocks that trade less than $20M a day.
- The system shall publish up to 10 long and 10 short ideas a day with a score of 60 or more; ideas with earnings within 5 days or against the regime go to a Watch list.
- The system shall run this as a desk step after the sector step and keep scores, ideas and reasons in `desk.db`.
- The system shall show the real idea list on the Market Floor.

### Acceptance Criteria

1. For 2 chosen dates, the score parts, setup, trigger and stop of three stocks match a hand check on the same candles.
2. The evening run adds the latest day of scores and ideas; earnings are checked for the latest day.
3. The Top ideas panels show real long and short ideas with the data date and no "Sample data" tag.

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
**Depends on:** DD-DSK §0.7 Q5 — the Master User approves every trade

- The system shall send only Master-approved ideas to the Execution tool as watchlist entries or trade signals.
- The system shall never let HELM place a trade without Master approval.
