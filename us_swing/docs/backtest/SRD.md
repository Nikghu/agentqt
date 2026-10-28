# Software Requirements Document — Backtest Module (BKT)

**Document ID:** SRD-BKT
**Version:** 1.0.0
**Traces To:** FO-BKT v1.0.0
**Status:** Draft
**Last Updated:** 2026-10-28
**Project:** US Swing Trading System

> v1.0.0: SRD-BKT-001.001–.011 added — backtest data store and downloader (Draft, waiting for user approval).

---

## FO-BKT-001 — Backtest Data Store and Downloader

| ID | Parent | P | Description | In | Out | Constraints | Status |
|---|---|---|---|---|---|---|---|
| SRD-BKT-001.001 | FO-BKT-001 | Must | 1d candles are stored as one Parquet file per stock and 3m candles as one file per stock per year under `~/.usswing/backtest/`. | bars | Parquet files | Never reads or writes `candles.db` | Implemented |
| SRD-BKT-001.002 | FO-BKT-001 | Must | Saving merges new bars with saved bars by timestamp, keeps one row per timestamp and replaces the file atomically. | bars | file | A crash mid-write leaves the old file intact | Implemented |
| SRD-BKT-001.003 | FO-BKT-001 | Must | Bars of the current US trading day are not saved before 16:15 US/Eastern. | bars, clock | filtered bars | Applies to 1d and 3m | Implemented |
| SRD-BKT-001.004 | FO-BKT-001 | Must | Settings hold start date, end date or latest, auto delta on/off, run time and run days, saved in `settings.json`. | settings | JSON file | Defaults 2016-01-01, latest, on, 17:30, Mon–Fri; bad file loads defaults | Implemented |
| SRD-BKT-001.005 | FO-BKT-001 | Must | The download plan asks for 1d in one request per stock, then 3m in 3-month chunks newest first, skipping ranges already saved. | settings, saved ranges | request list | Chunks before a stock's first available bar are skipped | Implemented |
| SRD-BKT-001.006 | FO-BKT-001 | Must | The downloader runs the plan in the background, waits and retries a failed request up to 3 times, then marks the stock failed and continues. | request list | bars, progress | Own TWS client ID; IBKR pacing limit respected | Implemented |
| SRD-BKT-001.007 | FO-BKT-001 | Must | A stop request ends the run after the current request; the next run continues from the saved files. | stop | stopped run | No saved month is downloaded twice | Implemented |
| SRD-BKT-001.008 | FO-BKT-001 | Must | Delta fill asks each stock for the days since its last saved bar, at least 2 days. | saved ranges | request list | Runs only when end date is latest | Implemented |
| SRD-BKT-001.009 | FO-BKT-001 | Must | Auto delta is due at the set US/Eastern time on set days, and a missed run is due at the next app start. | settings, last delta, clock | due yes/no | Off when auto delta is off or end date is fixed | Implemented |
| SRD-BKT-001.010 | FO-BKT-001 | Must | Clear deletes all saved candles and download state but keeps `settings.json`. | click | empty store | Refused while a download runs | Implemented |
| SRD-BKT-001.011 | FO-BKT-001 | Should | Stats give stock count, 1d and 3m bar counts, first and last date, disk size and last delta time. | store | stats | Read from Parquet metadata, not full files | Implemented |
