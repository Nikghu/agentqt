# Functional Overview — Market Analytics (MKT)

**Document ID:** FO-MKT
**Version:** 0.9.1
**Status:** Draft
**Last Updated:** 2026-11-11
**Project:** US Swing Trading System

> v0.24.1: FO-MKT-020 approved by user 2026-11-13.
> v0.24.0: AI Desk v3 M5 (user, 2026-11-13): FO-MKT-020 Company day added as Draft — stand-up, huddle, day call and its check, day-end handover and feedback.
> v0.23.0: AI Desk v3 M4 (user, 2026-11-13): FO-MKT-010 gains the sessions bullets as Draft — chat sessions, summary on close, memory notes, one team ask.
> v0.22.0: AI Desk v3 M3 (user, 2026-11-13): FO-MKT-012 gains the view check bullet as Draft.
> v0.21.0: AI Desk v3 M1 (user, 2026-11-13): FO-MKT-005 and FO-MKT-006 gain M1 message bullets as Draft (ask news review, send back a stop, fixed levels, news reply).
> v0.20.1: FO-MKT-019 approved by user 2026-11-12.
> v0.20.0: Strategy test (user, 2026-11-12): FO-MKT-019 added as Draft — strategy test research.
> v0.19.1: FO-MKT-018 approved by user 2026-11-11.
> v0.19.0: Autonomous desk step F (user, 2026-11-11): FO-MKT-018 added as Draft — book to strategy research.
> v0.18.1: FO-MKT-017 approved by user 2026-11-11.
> v0.18.0: Autonomous desk step F (user, 2026-11-11): FO-MKT-017 added as Draft — sentiment research.
> v0.17.1: FO-MKT-016 approved by user 2026-11-11.
> v0.17.0: Autonomous desk step F (user, 2026-11-11): FO-MKT-016 added as Draft — pick post-mortem research.
> v0.16.1: FO-MKT-015 approved by user 2026-11-11.
> v0.16.0: Autonomous desk step F (user, 2026-11-11): FO-MKT-015 added as Draft — setup tuning research.
> v0.15.1: FO-MKT-014 approved by user 2026-11-11.
> v0.15.0: Autonomous desk step E (user, 2026-11-11): FO-MKT-014 added as Draft — lead research tickets.
> v0.14.0: Autonomous desk step D (user, 2026-11-11): FO-MKT-013 added as Draft — check-ins and watchers.
> v0.13.0: Autonomous desk step C (user, 2026-11-11): FO-MKT-012 added as Draft — memory v1.
> v0.12.0: Autonomous desk step A (user, 2026-11-10): FO-MKT-001 runs in the morning run and adds the candle check with a Yahoo desk-only copy; FO-MKT-005 brief becomes the morning brief. Older acceptance lines that say "evening run" describe the run in place when they were written.
> v0.11.2: FO-MKT-011 Implemented (RN-MKT-0.12.0-20261110).
> v0.11.1: FO-MKT-011 approved by user 2026-11-10.
> v0.11.0: FO-MKT-011 added as Draft — Ask the Desk for New Data (P10).
> v0.10.1: FO-MKT-010 approved by user 2026-11-06.
> v0.10.0: FO-MKT-010 added as Draft — Lead Chat (P9).
> v0.9.1: FO-MKT-009 approved by user 2026-11-06.
> v0.9.0: FO-MKT-009 added as Draft — Pick Results (P8).
> v0.8.1: FO-MKT-008 approved by user 2026-11-06.
> v0.8.0: FO-MKT-008 written in full as Draft — Link to Execution (P7).
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
- The system shall run this as a desk step in the morning run and keep the results in `desk.db`.
- The system shall check, before any market step, that the daily candles reach the last closed trading day; stocks still behind get only their missing days from Yahoo Finance, kept as a desk-only copy so `candles.db` stays IBKR-only; when the candles are still not up to date the run stops before any AI call (user, 2026-11-10).
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
- The system shall add a lead brief skill that picks the final ideas only from ideas that passed the risk check, and writes the morning brief for the Floor (evening until 2026-11-10).
- The system shall ship default employees for the new skills with generic level names only; the Master user may rename, re-level or re-link them.
- (M1, messages on) The setup review shall ask the news review about an idea whose news it does not know, and grade that idea with the reply.
- (M1, messages on) The risk check shall send an idea whose stop breaks the stop limit back to the setup review for a fix, at most twice; the code limit keeps the final say.
- (M1, messages on) The system shall use a fixed trigger and stop for that idea everywhere for the rest of its data day.

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
- (M1, messages on) The news review shall answer an ask about listed ideas from its facts with one reply.

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

**Status:** Implemented (RN-MKT-0.9.0-20261106)
**Priority:** Should
**Phase:** P7
**Depends on:** DD-DSK §0.7 Q5 (the Master User approves every trade), FO-EXE-021, FO-GUI-034

The system shall show each lead pick to the Master user for approval and send only approved picks to Execution as pending trade signals. No AI employee approves a pick or places a trade; the Master places the order in Execution.

- The system shall list each lead pick that passed the risk check in Command → Approvals waiting until the Master decides or it expires.
- The system shall give each pick an entry at the idea trigger, a stop at the idea stop and a target at 2R, where the R multiple is one desk setting.
- The system shall allow both long and short picks.
- The system shall record each Master decision as a new `trade` row in the append-only `approvals` table.
- The system shall send an approved pick to Execution as one pending trade signal.
- The system shall expire a pick that is not decided by the next NYSE market open.
- The system shall never let any AI employee approve a pick or place a trade.

### Acceptance Criteria

1. After an evening run, each risk-passed lead pick shows in Approvals waiting with side, entry, stop, target and quantity.
2. Approve adds one pending signal under the AI Desk strategy in Execution and one `trade` approval row.
3. Reject adds one `trade` approval row and no signal.
4. After the next market open, an undecided pick can no longer be approved.
5. No code in the desk process writes a trade approval, a pending signal or an order.

## FO-MKT-009: Pick Results

**Status:** Implemented (RN-MKT-0.10.0-20261106)
**Priority:** Should
**Phase:** P8
**Depends on:** FO-MKT-005 (lead picks), FO-MKT-008 (trade approvals), FO-EXE-021 (AI Desk trades)

The system shall measure how the desk's lead picks turn out, both as paper results for every pick and as real results for the trades the Master user placed, so the desk's work can be judged by results. Results are shown by skill and input, never by employee name.

- The system shall work out a paper result for every lead pick from daily candles, whether the pick was approved, rejected or expired.
- The system shall count a paper pick as entered only when price reaches its trigger within 5 trading days after the pick.
- The system shall end an entered paper pick at its stop, its 2R target, or the close of its 10th trading day, whichever comes first.
- The system shall record the real result of each closed AI Desk trade against its pick.
- The system shall break results down by Master decision, setup review grade and news tone.
- The system shall show the results in a new AI Desk Results section and in the weekly report.

### Acceptance Criteria

1. After an evening run, every lead pick has a paper result: no fill, open, stop, target or time.
2. A pick whose trigger is not reached in 5 trading days shows no fill.
3. When an AI Desk trade closes in the app, a real result row with its P&L and R is added.
4. AI Desk → Results shows paper and real totals, the breakdowns and one row per pick.
5. The Friday weekly report has a pick results section for the week's picks.

## FO-MKT-010: Lead Chat

**Status:** Implemented (RN-MKT-0.11.0-20261106)
**Priority:** Should
**Phase:** P9
**Depends on:** FO-MKT-005 (lead brief and views), FO-MKT-009 (pick results), FO-DSK-003 (events)

The system shall let the Master user ask the lead questions in AI Desk and get answers from the desk, so the desk's views and picks can be questioned in plain words. The desk process answers, so every answer is recorded and counted in the desk budget. The chat only explains; it never acts.

- The system shall let the Master type a question in AI Desk → Command and send it to the desk.
- The system shall wake a lead-level chat employee for each question and answer it from the latest day's facts, the last 10 trading days of picks with their paper results, and the last few chat turns.
- The system shall show the answer under the question in Command.
- The system shall save a failed reply when no valid answer comes, and show an expired note when the desk does not answer in 30 minutes.
- The system shall never let the chat approve, reject or place a trade.
- The system shall limit the chat only by the chat employee's monthly cost cap and the desk budget.
- The system shall ship a default chat employee with a generic lead-level name only.

**Sessions (AI Desk v3 M4, user 2026-11-13):** one discussion per topic between the Master and the chat lead. AI summary on close; summary and stated preferences go to the lead's memory; the lead may send one ask to the team per question; session list and New discussion in Command. Behind the Chat sessions switch, off by default. Design: https://claude.ai/artifact/3dr7g92HY5hvVQ9KiyrPvc (M4).

- The system shall group chat questions into sessions: a new session after 2 hours of quiet or on a new New York day, unless the Master chose a session (AI Desk v3 M4).
- The system shall answer a question from its own session's summary and recent turns (AI Desk v3 M4).
- The system shall close a session after 24 hours of quiet or when the Master starts a new discussion, and write its summary with one AI call (AI Desk v3 M4).
- The system shall keep the summary and the Master's stated preferences as notes in the lead's memory while Memory v2 is on (AI Desk v3 M4).
- The system shall let the lead send one question to an expert per Master question and post the reply as an update; the chat still never trades (AI Desk v3 M4).

### Acceptance Criteria

1. With the desk running, a question sent in Command gets an answer in the chat within about a minute.
2. The answer can name the day's picks and their paper results.
3. With the desk stopped, the chat says to start the desk; the question expires after 30 minutes.
4. A failed or refused answer shows a failed reply, and the next question still works.
5. Nothing in the chat changes approvals, signals or orders.
6. With Chat sessions on, two topics in one day keep separate context, and a session reopened the next day continues from its summary (M4).
7. With Chat sessions off, the chat works as before (M4).

## FO-MKT-011: Ask the Desk for New Data

**Status:** Implemented (RN-MKT-0.12.0-20261110)
**Priority:** Could
**Phase:** P10
**Depends on:** FO-GUI-034 (Floor catalog), FO-MKT-003 (scores and ideas), FO-MKT-009 (pick results), FO-DSK-003 (events)

The system shall let the Master user ask the desk for a new Floor panel in plain words. A desk employee turns the request into a safe recipe from a fixed menu; code checks it and runs it read-only. The Master previews and approves it before it joins the Floor catalog. The model never writes SQL.

- The system shall let the Master type a data request in the Floor Add panel catalog and send it to the desk.
- The system shall wake a data employee for each request and have it fill a recipe: source, columns, filters, sort and row limit, from a fixed menu.
- The system shall check every recipe against the menu in code and run it read-only.
- The system shall show each proposed panel with its recipe in words and a preview in AI Desk → Approvals waiting for the Master to approve or reject.
- The system shall add approved panels to the Floor catalog, with rows from the latest data day each time they are shown.
- The system shall show the reason when the desk cannot build a request.
- The system shall ship a default data employee with a generic expert-level name only.

### Acceptance Criteria

1. With the desk running, a request such as "long scores above 80 in Technology" is proposed in Approvals waiting with a preview within a few minutes.
2. Approve adds the panel to the Floor catalog; Reject does not.
3. After the next evening run, an approved panel shows the new day's rows.
4. A request the menu cannot serve shows a failed note with the reason.
5. No model answer ever runs as SQL; only menu columns and tables are used.

## FO-MKT-012: Learning from Pick Results

**Status:** Implemented (approved by user 2026-11-11)
**Priority:** Must
**Phase:** Autonomous desk step C
**Depends on:** FO-MKT-009 (pick results), FO-MKT-005 (pick-making skills), FO-DSK-009 (lessons)
**Source: User 2026-11-11 (Autonomous desk step C, memory v1): lessons only for pick makers; active at 5 cases (backtest later); one reflect call a day after pick results. Design §8: https://claude.ai/artifact/J7AexvWdqDNujADoc9dJkJ.**

The system shall turn closed pick results into a few candidate lessons each day and give the active lessons to the skills that make picks.

- The system shall work out, in code, win rate and average R of closed picks by side, setup, regime, sector, setup review grade and news tone.
- The system shall ask one AI call a day, only on days with new closed picks, for at most 3 candidate lessons with their proof.
- The system shall check the reflect answer against a fixed form before any lesson is kept.
- The system shall ship a default expert-level employee that owns the reflect skill.
- The system shall add the matching active lessons to the facts of setup review, news review, risk check and the lead brief.
- The system shall check each open employee view against the daily closes 10 trading days after it was made: right at 1% or more its way, wrong at 1% or more the other way, else neutral (AI Desk v3 M3, user 2026-11-13).

### Acceptance Criteria

1. On a day with new closed picks the reflect employee runs once and adds at most 3 candidates.
2. On a day with no new closed picks it stays asleep and makes no call.
3. Regime view and sector view prompts hold no lessons.

## FO-MKT-013: Intraday Watchers and Check-in Notes

**Status:** Implemented (approved by user 2026-11-11)
**Priority:** Must
**Phase:** Autonomous desk step D
**Depends on:** FO-DSK-003 (events), FO-GUI-038 (app feeds), FO-MKT-005 (ideas and picks), FO-MKT-006 (news)
**Source: User 2026-11-11 (Autonomous desk step D): prices from the app's intraday candles; stop/target watcher covers all open trades; watchers every 5 minutes; an AI note at each check-in. Design §4 and §6: https://claude.ai/artifact/J7AexvWdqDNujADoc9dJkJ.**

The system shall watch the plan and the open trades during market hours with plain code, and ask the AI only when something happens.

- The system shall read the app's 3-minute bars for plan stocks, open-trade stocks and SPY.
- The system shall flag a trigger reached, a stop or target touched, a volume spike, a gap and a large SPY move.
- The system shall flag a new headline for a lead pick or an open-trade stock.
- The system shall ask one AI employee whether the plan still holds for each flag, and alert when it is broken.
- The system shall also send a broken plan or a stop or target touch to the flag employee's boss when escalation is on (AI Desk v3 M2, user 2026-11-13).
- The system shall write a short AI note at each check-in.
- The system shall never place, change or close a trade from a flag or a note.

### Acceptance Criteria

1. When a listed idea's price reaches its trigger, a feed note and an AI answer for it appear within about 5 minutes.
2. A stop touch on any open trade raises a "Trade at stop" alert on the app and Telegram.
3. Each trading day the feed has three check-in notes when the app is open from 10:00 to 15:30 New York time.

## FO-MKT-014: Lead Research Tickets

**Status:** Implemented (approved by user 2026-11-11)
**Priority:** Must
**Phase:** Autonomous desk step E
**Depends on:** FO-DSK-010 (research queue), FO-MKT-005 (lead plan), FO-MKT-013 (check-in notes)
**Source: User 2026-11-11 (Autonomous desk step E): leads raise research tickets. Design §7: https://claude.ai/artifact/J7AexvWdqDNujADoc9dJkJ.**

The system shall let the lead skills ask for research as tickets inside their normal answers.

- The system shall let a lead's plan or check-in answer hold a few research tickets.
- The system shall tell the lead its research tokens left today and its open tickets, so it does not ask twice or over its share.
- The system shall pass each ticket to the research queue and never start research work itself.

### Acceptance Criteria

1. A lead plan answer with one ticket adds one row to the research queue.
2. A lead with no research tokens left gets a prompt that says so, and a ticket it still raises is refused.

## FO-MKT-015: Setup Tuning Research

**Status:** Implemented (approved by user 2026-11-11)
**Priority:** Must
**Phase:** Autonomous desk step F (skill 1 of 4)
**Depends on:** FO-DSK-010 (research queue), FO-MKT-003 (setups), FO-MKT-012 (lessons), FO-BKT-002 (backtest engine)
**Source: User 2026-11-11 (Autonomous desk step F): first research skill is setup tuning; engine by ticket target, gain = +0.05R on 100+ trades, gain may write a candidate lesson, report only. Design §7, §9: https://claude.ai/artifact/J7AexvWdqDNujADoc9dJkJ.**

The system shall give the desk an employee that works setup tuning tickets: it tries a few changed limits for one setup or strategy, tests them in code and reports which one did better.

- The system shall let a setup tuning ticket name either a desk setup or a live execution strategy as its target.
- The system shall test a desk setup on the desk's own 5-year replay, and a strategy on the backtest engine.
- The system shall let AI only pick the variants and read the result table; code runs the tests and decides the gain.
- The system shall count a gain only when a variant beats the current limits by at least 0.05R over at least 100 trades.
- The system shall write a candidate lesson for a desk-setup gain, and never change a live setup or strategy.
- The system shall ship a default research employee with a generic name.

### Acceptance Criteria

1. An approved Pullback tuning ticket ends `done` with a result table of the baseline and up to 3 variants.
2. A variant that beats the baseline by 0.05R on 100 or more trades marks the ticket gain = yes and adds one candidate lesson.
3. After the ticket, the live setups and the strategy list are unchanged.

## FO-MKT-016: Pick Post-Mortem Research

**Status:** Implemented (approved by user 2026-11-11)
**Priority:** Must
**Phase:** Autonomous desk step F (skill 2 of 4)
**Depends on:** FO-DSK-010 (research queue), FO-MKT-009 (pick results), FO-MKT-012 (lessons)
**Source: User 2026-11-11 (Autonomous desk step F): pick post-mortem studies losers and winners of the last 30 days; bars from Backtest Data, candles.db only for missing days; may write candidate lessons, follow-up tickets and per-pick notes; gain = a lesson saved. Design §7: https://claude.ai/artifact/J7AexvWdqDNujADoc9dJkJ.**

The system shall give the desk an employee that works post-mortem tickets: it studies a chosen set of closed lead picks in depth and says why the losers failed compared with the winners.

- The system shall let the AI choose up to 10 losing and 5 winning closed lead picks of the last 30 days that fit the ticket's goal.
- The system shall gather, in code, each pick's stored desk facts and its price path after the data day.
- The system shall read price paths from Backtest Data first and from `candles.db` only for days Backtest Data does not have yet.
- The system shall let one AI call write a note per pick, up to 3 candidate lessons, up to 2 follow-up tickets and a summary.
- The system shall keep a lesson only when its proof picks are in the studied set, and count a gain only when a lesson is saved.
- The system shall ship a default post-mortem employee with a generic name.

### Acceptance Criteria

1. An approved post-mortem ticket on 4 losers and 2 winners ends `done` with one note per pick and a summary in its result.
2. A lesson that names a studied loser is saved as a candidate and the ticket gain is yes; a lesson naming an unknown pick is dropped.
3. A follow-up setup tuning ticket appears in the research queue under the lead that raised the post-mortem.

## FO-MKT-017: Sentiment Research

**Status:** Implemented (approved by user 2026-11-11)
**Priority:** Must
**Phase:** Autonomous desk step F (skill 3 of 4)
**Depends on:** FO-DSK-010 (research queue), FO-MKT-006 (news review), FO-MKT-005 (lead plan), FO-MKT-013 (open trades)
**Source: User 2026-11-11 (Autonomous desk step F): AI picks up to 30 stocks from today's ideas and open trades; stored headlines first, fetch only gaps; save tone cards the lead's next plan reads, scores unchanged; gain = a warning found. Design §7: https://claude.ai/artifact/J7AexvWdqDNujADoc9dJkJ.**

The system shall give the desk an employee that works sentiment tickets: it judges the news tone of chosen stocks for their idea's side and leaves short tone cards for the lead.

- The system shall let the AI choose up to 30 stocks from the latest listed and watch ideas and the open trades that fit the ticket's goal.
- The system shall use the desk's stored headlines first and fetch fresh ones only for stocks with no recent stored headline.
- The system shall let one AI call judge each stock's news as supporting, neutral or against its side, with a short reason.
- The system shall save one tone card per judged stock and show the cards of the last 7 days in the lead's plan prompt, without changing idea scores.
- The system shall count a gain only when at least one stock's news is against its side.
- The system shall ship a default sentiment employee with a generic name.

### Acceptance Criteria

1. An approved sentiment ticket on 5 watch ideas ends `done` with 5 tone cards and a summary in its result.
2. A long idea with bad news is judged against, and the ticket gain is yes.
3. The next lead plan prompt shows that stock's card; its idea score is unchanged.

## FO-MKT-018: Book to Strategy Research

**Status:** Implemented (approved by user 2026-11-11)
**Priority:** Must
**Phase:** Autonomous desk step F (skill 4 of 4)
**Depends on:** FO-DSK-010 (research queue; book tickets never auto-approve), FO-MKT-005 (lead plan), FO-MKT-014 (lead tickets)
**Source: User 2026-11-11 (Autonomous desk step F): ticket approval is the permission to read; text only from the user's uploads or Project Gutenberg (public domain); text, HTML and PDF; output a strategy card only; gain = card with entry, exit and stop. Design §7: https://claude.ai/artifact/J7AexvWdqDNujADoc9dJkJ.**

The system shall give the desk an employee that turns one approved chapter of a trading book into a short strategy card, and never reads a book without the owner's approval.

- The system shall read a book chapter only for an approved book ticket that names its source and chapter.
- The system shall take book text only from the owner's uploads in the desk books folder or from a public-domain Project Gutenberg download.
- The system shall read plain text, Markdown, HTML and PDF files.
- The system shall read each chapter once and never read it again.
- The system shall let one AI call write a strategy card with idea, market, entry, exit, stop and short quotes from the chapter, and keep only quotes found in the text.
- The system shall show the lead which books it may propose and which chapters were already read.
- The system shall ship a default book employee with a generic name.

### Acceptance Criteria

1. An approved ticket `upload:my_book.txt ch 2` ends `done` with one strategy card in its result and in `strategy_cards`.
2. A second ticket for the same chapter ends `failed` without reading the file again.
3. A ticket naming any other website ends `failed` and nothing is downloaded.

## FO-MKT-019: Strategy Test Research

**Status:** Implemented (approved by user 2026-11-12)
**Priority:** Must
**Phase:** Research skills (T160, strategy test)
**Depends on:** FO-MKT-018 (strategy cards), FO-MKT-015 (replay on Backtest Data), FO-DSK-010 (research queue), FO-SCR-013 / FO-SCR-014 (indicator rules, price patterns)
**Source: User 2026-11-12: test strategy cards on all Backtest Data; pass = at least 30 trades, average R above 0.2 and better than a simple baseline; the lead raises tests after new cards and the owner can raise one from a card; Cards view as a second step.**

The system shall give the desk an employee that tests one strategy card on past data and says plainly whether it worked, without ever touching live trading.

- The system shall turn a card into a test recipe built only from the existing indicator rules and price patterns, with no free code.
- The system shall end the test as "can't test" and name the part when a card rule has no matching block.
- The system shall replay the recipe on all Backtest Data daily bars of S&P 500 stocks with a fixed stop, target and time exit.
- The system shall compare the card with a simple baseline and let code alone decide pass or fail.
- The system shall keep each test result with its card and turn a pass into a candidate lesson.
- The system shall let the lead raise a test for a new card and let the owner raise one from the app.
- The system shall ship a default strategy test employee with a generic name.

### Acceptance Criteria

1. An approved ticket `SC-3` ends `done` with a table of trades, win rate, average R, worst losing run and baseline, and a pass or fail.
2. A card whose entry needs a block that does not exist ends `failed` with "can't test" and the part named.
3. No live strategy, setting or trade changes during or after a test.

## FO-MKT-020: Company Day

**Status:** Approved (user, 2026-11-13)
**Priority:** Must
**Phase:** AI Desk v3 M5
**Depends on:** FO-MKT-005 (views and lead brief), FO-MKT-013 (watchers and check-ins), FO-DSK-011 (agent messages), FO-DSK-009 (memory v2), FO-DSK-003 (events)
**Source: User 2026-11-13 (AI Desk v3 M5): stand-up built by code with no AI call; a one-round huddle only when code finds a clash between experts, at most one a day; the lead's day call and the huddle are logged with who agreed and checked after 5 trading days; one lead AI call at day-end writes the handover note and one feedback line per expert. Plan: https://claude.ai/artifact/3dr7g92HY5hvVQ9KiyrPvc (M5).**

The system shall give the desk a daily rhythm: a stand-up before the plan, a short huddle when experts clash, a logged day call that is checked later, and a day-end handover read the next morning. Behind the Company day switch, off by default.

- The system shall build a stand-up before the lead brief from yesterday's handover note and two short lines per expert view, with no AI call.
- The system shall call a one-round huddle of the regime view and sector/flow experts when their views clash, at most once a day, and let the lead decide after the replies.
- The system shall keep the lead's day call (market view and favoured sectors) with who agreed and who disagreed.
- The system shall check each day call after 5 trading days against SPY and sector moves and add the result to each expert's track record.
- The system shall run a day-end after the close, or at the next start when the app was closed: a code status, one lead AI call for the handover note and one feedback line per expert, kept in the expert's memory.
- The system shall never place, change or close a trade from the company day.

### Acceptance Criteria

1. With Company day on, the lead brief facts start with the stand-up, and yesterday's handover note is in it.
2. On a day with a clash and messages on, exactly one huddle runs; both experts reply once; the lead brief runs after the replies and its day call is saved.
3. A day call 5 trading days old is marked right, wrong or neutral, and each voting expert's core block shows its day-call record.
4. After the close, one day-end AI call writes a handover note that the next morning's stand-up shows.
5. With Company day off, the morning run and the lead brief work as before.

