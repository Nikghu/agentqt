# Functional Overview — Market Analytics (MKT)

**Document ID:** FO-MKT
**Version:** 0.5.0
**Status:** Draft
**Last Updated:** 2026-11-06
**Project:** US Swing Trading System

> v0.7.0: FO-MKT-007 written in full as Draft and renamed by function, AI Report Pages (P5d).
> v0.6.1: FO-MKT-005 reworded by skill and level; no employee names (user, 2026-11-06).
> v0.6.0: FO-MKT-005 written as Draft for its first skill, the regime view (P5a); the other experts, risk manager and lead stay for P5b.
> v0.5.0: FO-MKT-004 written in full as Draft (daily candles from the Backtest Data store; bands, setups and idea status; pass rule at 10 days; Score proof panel; no tuning).
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

**Status:** Approved (user, 2026-11-06)
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

**Status:** Implemented (approved by user 2026-11-06)
**Priority:** Must
**Phase:** P4
**Depends on:** FO-MKT-001–003 (score rules), FO-BKT-001 (daily candles in the Backtest Data store)

The system shall replay the P1–P3 score on years of past daily candles and show whether high scores were followed by better moves, before any AI is added. No AI is used and no rule is tuned in P4.

- The system shall read daily candles of the S&P 500 members and SPY from the Backtest Data store, read only.
- The system shall recompute regime, sectors, RS ratings, scores, setups and the idea list for every past day, using only data up to that day.
- The system shall measure the 5, 10 and 20-day return of every scored stock-day per side, entering at the next day's open, and its return against SPY.
- The system shall report count, win rate, average return and average return against SPY by score band, by setup and by idea status.
- The system shall give each side a pass or fail: at 10 days, stocks scoring 70+ beat SPY on average and beat stocks scoring under 40.
- The system shall keep each run's results in `desk.db`; `desk proof` runs it and prints the report.
- The system shall show the latest proof on the Market Floor in a Score proof panel.
- The system shall warn when daily history is shorter than 5 years and say how to download more.

### Acceptance Criteria

1. For 3 chosen stock-days, the forward returns and returns against SPY match a hand check on the same candles.
2. On 3 recent days, at least 90% of the replayed scores are within 1 point of the desk's stored scores; differences come only from the candle source.
3. `desk proof` prints the band, setup and status tables with the pass result per side; the Score proof panel shows the same with the data range.
4. With less than 5 years of daily data, the report and the panel show the download reminder.

**Data note (user to do).** The Backtest Data store now starts on 2024-01-02. After the 1-year warm-up for RS ratings that leaves under 2 years of scored days. To test on 5–6 years, set Start date in Settings → Backtest Data to 2020-01-01 and download. That setting also downloads 3-minute bars for those years, which is very large (TODO T118).

**Limits.** Today's S&P 500 list only (survivorship bias). No past earnings dates, so the earnings Watch rule is not applied. Daily samples overlap, so they are not independent. No costs, slippage or stop exits.

## FO-MKT-005: AI Experts, Risk Manager and Trade Manager

**Status:** Regime view part Implemented (approved by user 2026-11-06); P5b part Implemented (approved by user 2026-11-06)
**Priority:** Must
**Phase:** P5a (regime view expert); P5b (sector/flow view, setup review, risk check, lead brief)
**Depends on:** FO-DSK-002–005, FO-MKT-001–004

The system shall add AI experts on top of the funnel. P5a adds the first skill, the regime view, used by one expert-level employee. P5b adds four more skills by function. Who does the work, and under what name, is data the Master user controls.

- The system shall wake the regime view employee after each desk run to read the regime, breadth, fear, sectors, idea counts and the latest proof.
- The system shall have it give a typed view: regime, confidence and up to 3 reasons, plus a short brief.
- The system shall keep each view with the rule regime and whether the view agrees.
- The system shall show the brief in the AI feed under the employee's current name, and say so when the view disagrees with the rule regime.
- The system shall add a sector/flow view skill that names the sectors to favour and to avoid, from sector ranks, quadrants and money flow.
- The system shall add a setup review skill that grades each listed idea A, B or C with a one-line note.
- The system shall add a risk check skill: hard risk limits kept in code veto ideas first, then the AI may veto more ideas with a reason but never undo a code veto.
- The system shall add a lead brief skill that picks the final ideas only from ideas that passed the risk check, and writes the evening brief for the Floor.
- The system shall ship default employees for the new skills with generic level names only; the Master user may rename, re-level or re-link them.

### Acceptance Criteria

1. One full regime view run on real data with a real model is recorded in `activity` within budget.
2. The AI feed on the Market Floor shows the brief with the employee's name, time and data day.
3. `regime_view` holds the typed view; a disagreement with the rule regime shows in the brief.
4. One evening run on real data wakes the sector/flow, setup review, risk check and lead employees in that order; each view is saved in `desk.db`.
5. An idea that breaks a hard limit is vetoed by code even when the AI says pass; the lead never picks a vetoed idea.
6. The evening brief shows on the Floor under the lead employee's current name, with the picks and their reasons.

## FO-MKT-006: News, Economic Calendar and Event Risk

**Status:** Implemented (approved by user 2026-11-06)
**Priority:** Should
**Phase:** P5c
**Depends on:** FO-MKT-003, FO-MKT-005, FO-DSK-002–005

The system shall add news and the economic calendar to the evening funnel. Free sources only (Yahoo Finance and public RSS feeds); a news review skill tags the listed ideas, and code turns the tags and event risk into the 10 news points of the score. Who does the work, and under what name, is data the Master user controls.

- The system shall collect recent headlines for each listed idea and recent market headlines after each Ideas step, and keep them in `desk.db` for 30 days.
- The system shall keep a yearly economic calendar in code (FOMC decisions, CPI, jobs report, PCE, GDP) with the importance of each event.
- The system shall add a news review skill that tags each listed idea positive, neutral or negative with a short reason, and writes a short market note.
- The system shall turn each tag and the next day's high-impact events into 0 to 10 news points, and give each listed idea a final score that includes them.
- The system shall let the risk check and the lead brief read the news tags and final scores.
- The system shall show headlines, tags and the coming economic events in the Market Floor "News & Calendar" tab.
- The system shall ship a default employee for the new skill with a generic level name only.

### Acceptance Criteria

1. After an evening run, `desk.db` holds the day's headlines for the listed ideas and the market, and nothing older than 30 days.
2. The news review employee tags every listed idea; each tag has its points and final score, and its market note shows in the AI feed.
3. On a day before a CPI release, every listed idea loses the event points.
4. The News & Calendar tab shows real headlines, tags and the next two weeks of economic events.

## FO-MKT-007: AI Report Pages

**Status:** Implemented (approved by user 2026-11-06)
**Priority:** Could
**Phase:** P5d
**Depends on:** FO-MKT-005, FO-DSK-002–005, FO-GUI-034

The system shall turn each evening's lead brief into one report page (HTML and CSS, with tables and simple charts) and show it in a sealed view in AI Desk. A report page skill writes the page, and code cleans it before it is kept and before it is shown. Who does the work, and under what name, is data the Master user controls.

- The system shall add a report page skill that writes one HTML/CSS page per data day from the lead brief and the day's views.
- The system shall clean every page in code before it is kept and before it is shown: no scripts, no event handlers, no outside or local links and images.
- The system shall keep every page version in `desk.db`; a new version never changes an old one.
- The system shall keep the last good page when a new answer is missing or fails the checks.
- The system shall show the pages in an AI Desk Pages section: a list of pages with their versions, and a view-only preview of the chosen version.
- The system shall show each page in a sealed view with JavaScript off and no network or local file access.
- The system shall ship a default employee for the new skill with a generic level name only.

### Acceptance Criteria

1. After an evening run, `desk.db` holds a new page version for the day, written after the lead brief.
2. A page with a script, an event handler, or an outside link or image is cleaned before it is kept, and none of it reaches the view.
3. AI Desk → Pages lists the day's page with its versions, and the preview shows the chosen version.
4. In the real window, the sealed view makes no network or local file request.
5. A missing or invalid answer keeps the previous good version and posts no brief, so a later run tries again.

## FO-MKT-008: Link to Execution

**Status:** Draft (outline)
**Priority:** Should
**Phase:** P7
**Depends on:** DD-DSK §0.7 Q5 — the Master User approves every trade

- The system shall send only Master-approved ideas to the Execution tool as watchlist entries or trade signals.
- The system shall never let any AI employee place a trade without Master approval.
