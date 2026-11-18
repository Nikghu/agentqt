# Revision Note — RN-SCR-2.8.0-20261118

**Version:** 2.8.0
**Date:** 2026-11-18
**Tool:** SCR
**Artifact:** FO-SCR-015 / SRD-SCR-017.014–.016
**Type:** Feature

---

## Summary

The Accumulation / Distribution screener can judge rally and drop days against each stock's own normal move. With "Stock's own move" (the new default), a day counts only when it moves at least the move factor (0.5×) times the stock's average daily move over the previous volume-average days. "Fixed %" keeps the old rule, and presets saved before this change stay on it.

---

## Modified Files

| MD ID | File | Change |
|---|---|---|
| MD-SCR-017.001.M32 | `src/us_swing/screener/screeners/acc_dist.py` | Added: `move_rule`, `move_factor`, `_move_threshold()`; old configs read as fixed |
| MD-SCR-017.013.M33 | `src/us_swing/gui/acc_dist_settings_dialog.py` | Added: Move rule choice; only the matching move input is enabled |

---

## Requirements Addressed

| SRD ID | Description | Status |
|---|---|---|
| SRD-SCR-017.014 | Own move rule with move factor | Implemented (approved by user 2026-11-18) |
| SRD-SCR-017.015 | Fixed rule kept; old configs read as fixed | Implemented (approved by user 2026-11-18) |
| SRD-SCR-017.016 | Move rule choice in the settings dialog | Implemented (approved by user 2026-11-18) |

---

## Tests

4 new UT cases Pass (UT-SCR-017.014.M32.T01–T02, .015.M32.T01, .016.M33.T01); all 25 Acc / Dist tests pass. Ruff and mypy --strict clean on both files.

## Check on real data (candles to 2026-11-17, user's Distribution preset settings)

After the price / volume first stage, 332 stocks: Fixed 0.5 % → 31 matches, Stock's own move 0.5× → 32 matches. 27 names are in both. New with own move: TECH, AES, AEE, TXN, HD. Dropped: XLV, BRK.B, FOXA, CB.
