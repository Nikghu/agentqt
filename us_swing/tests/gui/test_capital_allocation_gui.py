"""
GUI-side tests for FO-EXE-017 — RiskConfig migration, Rex display, effective
capital + daily-loss aggregation.
Parent SRD: SRD-EXE-017.001, .002, .007, .011, .014, .027
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QObject
from pytestqt.qtbot import QtBot

from us_swing.data.models import AccountState, OpenPosition, RiskConfig, UserProfile
from us_swing.gui.active_cycles_model import _ActiveCyclesModel, _Row
from us_swing.gui.app_service import AppService
from us_swing.gui.user_store import _from_dict, _to_dict


# ── RiskConfig migration (user_store) ─────────────────────────────────────────

def test_legacy_settings_migrates_to_absolute_capital() -> None:
    """UT-EXE-017.014.M07.T01: legacy max_allocation_pct → default max_capital_value."""
    legacy = {
        "user_id": 1, "username": "Alice", "display_name": "Alice",
        "ibkr_client_id": 101, "mode": "paper",
        "risk_per_trade_pct": 1.0, "max_position_value": 10_000.0,
        "max_allocation_pct": 50.0, "max_daily_loss_pct": 2.0,
        "default_order_type": "MKT", "confirm_orders": True,
    }
    profile = _from_dict(legacy)
    assert profile.risk_config.max_capital_value == 2_000.0
    assert not hasattr(profile.risk_config, "max_allocation_pct")


def test_max_capital_round_trip() -> None:
    """UT-EXE-017.014.M07.T02: max_capital_value survives serialize/deserialize."""
    profile = UserProfile(
        1, "Alice", "Alice", 101, "paper",
        risk_config=RiskConfig(max_capital_value=3_500.0),
        strategy_config={}, screener_config={},
    )
    restored = _from_dict(_to_dict(profile))
    assert restored.risk_config.max_capital_value == 3_500.0


# ── Rex column display ────────────────────────────────────────────────────────

def _model(qtbot: QtBot) -> _ActiveCyclesModel:
    return _ActiveCyclesModel(query=MagicMock(), pending_store=MagicMock())


def test_rex_exhausted_shows_zero(qtbot: QtBot) -> None:
    """UT-EXE-017.011.M05.T01: an exhausted counter renders 0, not -1."""
    m = _model(qtbot)
    row = _Row(kind="cycle", key="k1", state="OPEN", symbol="CVS",
               strategy="SUPERTREND", rex_remaining=-1)
    assert m._rex_display(row) == "0"


def test_rex_positive_shows_value(qtbot: QtBot) -> None:
    """UT-EXE-017.011.M05.T02: a positive remaining renders verbatim."""
    m = _model(qtbot)
    row = _Row(kind="cycle", key="k1", state="OPEN", symbol="CVS",
               strategy="SUPERTREND", rex_remaining=2)
    assert m._rex_display(row) == "2"


def test_rex_pending_duplicate_suppressed(qtbot: QtBot) -> None:
    """UT-EXE-017.011.M05.T03: a pending dup of an open (strategy, symbol) shows —."""
    m = _model(qtbot)
    open_row = _Row(kind="cycle", key="k1", state="OPEN", symbol="CVS",
                    strategy="SUPERTREND", rex_remaining=-1)
    pending_row = _Row(kind="pending", key="k2", state="PENDING", symbol="CVS",
                       strategy="SUPERTREND", rex_remaining=-1)
    m._rows = [open_row, pending_row]
    assert m._rex_display(pending_row) == "—"


# ── effective capital + daily loss ────────────────────────────────────────────

def _svc(active_uid: int, users: list[UserProfile], ibkr_acct: AccountState | None = None,
         tc_query: object | None = None) -> AppService:
    svc = AppService.__new__(AppService)
    QObject.__init__(svc)
    svc._users = users          # type: ignore[attr-defined]
    svc._active_uid = active_uid  # type: ignore[attr-defined]
    svc._viewing_uid = None       # type: ignore[attr-defined]
    svc._ibkr_acct = ibkr_acct    # type: ignore[attr-defined]
    svc._tc_query = tc_query      # type: ignore[attr-defined]
    svc._daily_loss_warned = False  # type: ignore[attr-defined]
    svc._positions = []           # type: ignore[attr-defined]
    svc._ibkr_positions = []      # type: ignore[attr-defined]
    return svc


def _paper_user() -> UserProfile:
    return UserProfile(1, "Alice", "Alice", 101, "paper",
                       risk_config=RiskConfig(max_capital_value=2_000.0),
                       strategy_config={}, screener_config={})


def _live_user(cap: float) -> UserProfile:
    return UserProfile(2, "Bob", "Bob", 102, "live",
                       risk_config=RiskConfig(max_capital_value=cap),
                       strategy_config={}, screener_config={})


def test_effective_capital_paper_uses_max_capital(qtbot: QtBot) -> None:
    """UT-EXE-017.001.M09.T01: paper budget equals stored Max Capital."""
    svc = _svc(1, [_paper_user()])
    assert svc.effective_capital() == 2_000.0


def test_effective_capital_live_within_cash(qtbot: QtBot) -> None:
    """UT-EXE-017.001.M09.T02: live budget within cash kept as-is."""
    acct = AccountState(2, 5_000.0, 5_000.0, 0.0, total_cash_value=5_000.0)
    svc = _svc(2, [_live_user(3_000.0)], ibkr_acct=acct)
    assert svc.effective_capital() == 3_000.0


def test_effective_capital_live_over_cash_uses_90pct(qtbot: QtBot) -> None:
    """UT-EXE-017.002.M09.T03: live budget over cash falls to 90% of cash."""
    acct = AccountState(2, 3_000.0, 3_000.0, 0.0, total_cash_value=3_000.0)
    svc = _svc(2, [_live_user(5_000.0)], ibkr_acct=acct)
    assert svc.effective_capital() == 2_700.0
    # stored setting unchanged
    assert svc.get_active_user().risk_config.max_capital_value == 5_000.0


# ── paper open-position value + margin_available ──────────────────────────────

class _FakeCycleSource:
    def __init__(self, positions: list[object]) -> None:
        self._positions = positions

    def get_all(self, user_id: int) -> list[object]:
        return self._positions


def test_paper_open_position_value_summed(qtbot: QtBot) -> None:
    """UT-EXE-017.019.M14.T01: paper open_position_value sums the open cycles."""
    svc = _svc(1, [_paper_user()])
    svc._cycle_position_source = _FakeCycleSource([          # type: ignore[attr-defined]
        MagicMock(average_price=100.0, quantity=5),   # $500
        MagicMock(average_price=80.0, quantity=10),   # $800
    ])
    assert svc.get_account_state(1).open_position_value == 1_300.0


def test_app_margin_available_nets_deployed(qtbot: QtBot) -> None:
    """UT-EXE-017.021.M14.T02: AppService.margin_available nets deployed value."""
    svc = _svc(1, [_paper_user()])
    svc._cycle_position_source = _FakeCycleSource([          # type: ignore[attr-defined]
        MagicMock(average_price=100.0, quantity=13),  # $1300
    ])
    assert svc.margin_available() == 700.0


def test_app_margin_available_floors_zero(qtbot: QtBot) -> None:
    """UT-EXE-017.021.M14.T03: margin floors at zero when over-deployed."""
    svc = _svc(1, [_paper_user()])
    svc._cycle_position_source = _FakeCycleSource([          # type: ignore[attr-defined]
        MagicMock(average_price=100.0, quantity=25),  # $2500
    ])
    assert svc.margin_available() == 0.0


class _FakeQuery:
    def __init__(self, open_pnl: float, closed_pnl: float) -> None:
        self._open = [MagicMock(current_pnl_usd=open_pnl)]
        self._closed = [MagicMock(realized_pnl_usd=closed_pnl)]

    def open_cycles(self) -> list[object]:
        return self._open

    def closed_between(self, start: str, end: str) -> list[object]:
        return self._closed


def test_daily_loss_warns_on_crossing(qtbot: QtBot) -> None:
    """UT-EXE-017.007.M09.T04: aggregate loss crossing the limit emits one warning."""
    # paper user, max_capital_value=$2000 → start_of_day_equity=$2000;
    # max_daily_loss 2% → threshold = -$40; aggregate loss -$60 crosses it.
    user = UserProfile(1, "Alice", "Alice", 101, "paper",
                       risk_config=RiskConfig(max_capital_value=2_000.0,
                                              max_daily_loss_pct=2.0),
                       strategy_config={}, screener_config={})
    svc = _svc(1, [user], tc_query=_FakeQuery(open_pnl=-40.0, closed_pnl=-20.0))
    raised: list[tuple[str, str]] = []
    svc.risk_warning_raised.connect(lambda k, m: raised.append((k, m)))
    svc._check_daily_loss()
    svc._check_daily_loss()   # second call must not double-warn
    assert len(raised) == 1
    assert raised[0][0] == "daily_loss"


def test_daily_loss_no_warn_within_limit(qtbot: QtBot) -> None:
    """UT-EXE-017.007.M09.T05: within the limit emits no warning."""
    user = UserProfile(1, "Alice", "Alice", 101, "paper",
                       risk_config=RiskConfig(max_capital_value=2_000.0,
                                              max_daily_loss_pct=2.0),
                       strategy_config={}, screener_config={})
    svc = _svc(1, [user], tc_query=_FakeQuery(open_pnl=-5.0, closed_pnl=-5.0))
    raised: list[tuple[str, str]] = []
    svc.risk_warning_raised.connect(lambda k, m: raised.append((k, m)))
    svc._check_daily_loss()
    assert raised == []


# ── paper account state follows today's P&L (SRD-EXE-017.027) ─────────────────

def _open(symbol: str, qty: int, avg: float, cur: float, uid: int = 1,
          direction: str = "LONG") -> OpenPosition:
    return OpenPosition(symbol=symbol, user_id=uid, quantity=qty, average_price=avg,
                        stop_loss=0.0, target_price=0.0, mode="paper", trailing_stop=False,
                        current_price=cur, direction=direction)


class _ClosedToday:
    def __init__(self, closes: list[tuple[int, float | None]]) -> None:
        self._closed = [MagicMock(user_id=u, realized_pnl_usd=p) for u, p in closes]

    def open_cycles(self) -> list[object]:
        return []

    def closed_between(self, start: str, end: str) -> list[object]:
        return self._closed


def test_paper_account_follows_pnl(qtbot: QtBot) -> None:
    """UT-EXE-017.027.M14.T01: paper equity, cash, P&L and positions value move with trades."""
    svc = _svc(1, [_paper_user()], tc_query=_ClosedToday([(1, 42.10), (1, None), (2, 500.0)]))
    svc._positions = [_open("NDAQ", 19, 102.78, 103.23, direction="SHORT"),   # −8.55
                      _open("AAPL", 2, 200.0, 210.0)]                          # +20.00
    svc._cycle_position_source = _FakeCycleSource([          # type: ignore[attr-defined]
        MagicMock(average_price=102.78, quantity=19), MagicMock(average_price=200.0, quantity=2),
    ])
    acct = svc.get_account_state(1)
    assert acct.start_of_day_equity == 2_000.0
    assert acct.daily_pnl == pytest.approx(42.10)
    assert acct.equity == pytest.approx(2_000.0 + 42.10 - 8.55 + 20.0)
    assert acct.open_position_value == pytest.approx(1_952.82 + 400.0)
    assert acct.total_cash_value == pytest.approx(2_000.0 + 42.10 - 2_352.82)
    assert acct.gross_position_value == pytest.approx(19 * 103.23 + 2 * 210.0)
    assert acct.capital_utilisation_pct > 0


def test_paper_account_all_users_and_no_ledger(qtbot: QtBot) -> None:
    """UT-EXE-017.027.M14.T02: All users sums every budget; no ledger means no realised P&L."""
    users = [_paper_user(), UserProfile(3, "Cara", "Cara", 103, "paper",
                                        risk_config=RiskConfig(max_capital_value=1_000.0),
                                        strategy_config={}, screener_config={})]
    svc = _svc(1, users)
    svc._cycle_position_source = _FakeCycleSource([          # type: ignore[attr-defined]
        MagicMock(average_price=10.0, quantity=10),
    ])
    acct = svc.get_account_state(None)
    assert acct.start_of_day_equity == 3_000.0
    assert acct.daily_pnl == 0.0
    assert acct.open_position_value == 200.0   # one $100 position per user from the fake source


def test_paper_account_counts_only_own_ibkr_positions(qtbot: QtBot) -> None:
    """UT-EXE-017.027.M14.T03: broker positions of other users do not move this user's equity."""
    svc = _svc(1, [_paper_user()])
    svc._ibkr_positions = [_open("AAPL", 2, 200.0, 210.0, uid=1),   # type: ignore[attr-defined]
                           _open("MSFT", 1, 100.0, 150.0, uid=2)]
    svc._cycle_position_source = _FakeCycleSource([])          # type: ignore[attr-defined]
    acct = svc.get_account_state(1)
    assert acct.equity == pytest.approx(2_000.0 + 20.0)
    assert acct.gross_position_value == pytest.approx(420.0)
