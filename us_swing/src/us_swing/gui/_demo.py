"""
Module: MD-GUI demo data — _demo.py
Mock backend services with realistic demo data for UI review.
Provides self-contained data so the GUI runs without any real backend.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from us_swing.data.models import (
    AccountState,
    OpenPosition,
    RiskConfig,
    ScreenerResult,
    TradeRecord,
    TradeSignal,
    UserProfile,
)
from us_swing.gui.user_store import load_users, next_user_id, save_users
from us_swing.gui.system_store import SystemConfig, load_system_config


# ── Static seed data ──────────────────────────────────────────────────────────

_USERS: list[UserProfile] = [
    UserProfile(1, "Alice", "Alice", 101, "paper",
                risk_config=RiskConfig(risk_per_trade_pct=1.0, max_allocation_pct=50.0),
                strategy_config={}, screener_config={}),
    UserProfile(2, "Bob",   "Bob",   102, "paper",
                risk_config=RiskConfig(risk_per_trade_pct=1.5, max_allocation_pct=40.0),
                strategy_config={}, screener_config={}),
    UserProfile(3, "Carol", "Carol", 103, "paper",
                risk_config=RiskConfig(risk_per_trade_pct=0.5, max_allocation_pct=30.0),
                strategy_config={}, screener_config={}),
]

_now = datetime.now()

_POSITIONS: list[OpenPosition] = [
    # ── Alice (user_id=1, LIVE) ────────────────────────────────────────────────
    OpenPosition(
        symbol="AAPL", user_id=1, quantity=200, filled_quantity=200, total_quantity=200,
        average_price=182.50, current_price=187.30, stop_loss=178.00, target_price=195.00,
        strategy_id="BREAKOUT", entry_time=_now - timedelta(days=2),
        mode="live",
    ),
    OpenPosition(
        symbol="MSFT", user_id=1, quantity=100, filled_quantity=100, total_quantity=150,
        average_price=415.00, current_price=418.75, stop_loss=405.00, target_price=435.00,
        strategy_id="PULLBACK", entry_time=_now - timedelta(days=1),
        mode="live",
    ),
    OpenPosition(
        symbol="NVDA", user_id=1, quantity=80, filled_quantity=80, total_quantity=80,
        average_price=875.00, current_price=856.40, stop_loss=850.00, target_price=920.00,
        strategy_id="BREAKOUT", entry_time=_now - timedelta(days=3),
        mode="live",
    ),
    OpenPosition(
        symbol="GOOGL", user_id=1, quantity=40, filled_quantity=40, total_quantity=100,
        average_price=178.00, current_price=176.50, stop_loss=172.00, target_price=188.00,
        strategy_id="PULLBACK", entry_time=_now - timedelta(hours=4),
        mode="live",
    ),
    # ── Bob (user_id=2, PAPER) ─────────────────────────────────────────────────
    OpenPosition(
        symbol="TSLA", user_id=2, quantity=50, filled_quantity=50, total_quantity=50,
        average_price=162.00, current_price=168.40, stop_loss=155.00, target_price=182.00,
        strategy_id="BREAKOUT", entry_time=_now - timedelta(days=1),
        mode="paper",
    ),
    OpenPosition(
        symbol="AMZN", user_id=2, quantity=80, filled_quantity=80, total_quantity=80,
        average_price=188.50, current_price=185.20, stop_loss=182.00, target_price=200.00,
        strategy_id="PULLBACK", entry_time=_now - timedelta(hours=6),
        mode="paper",
    ),
    # ── Carol (user_id=3, PAPER) ───────────────────────────────────────────────
    OpenPosition(
        symbol="SPY", user_id=3, quantity=100, filled_quantity=100, total_quantity=100,
        average_price=495.00, current_price=498.80, stop_loss=488.00, target_price=510.00,
        strategy_id="BREAKOUT", entry_time=_now - timedelta(days=2),
        mode="paper",
    ),
    OpenPosition(
        symbol="QQQ", user_id=3, quantity=40, filled_quantity=40, total_quantity=60,
        average_price=420.00, current_price=425.30, stop_loss=413.00, target_price=440.00,
        strategy_id="PULLBACK", entry_time=_now - timedelta(hours=3),
        mode="paper",
    ),
]

_TRADES: list[TradeRecord] = [
    # Alice
    TradeRecord(trade_id="1001", user_id=1, symbol="META",  side="BUY", quantity=120,
                entry_price=505.00, mode="live", strategy_id="BREAKOUT",
                entry_time=_now - timedelta(days=1),  exit_time=_now - timedelta(hours=2),
                exit_price=521.30, order_state="FILLED", filled_quantity=120),
    TradeRecord(trade_id="1002", user_id=1, symbol="AMZN",  side="BUY", quantity=50,
                entry_price=188.50, mode="live", strategy_id="PULLBACK",
                entry_time=_now - timedelta(hours=6),  exit_time=_now - timedelta(hours=1),
                exit_price=192.10, order_state="FILLED", filled_quantity=50),
    TradeRecord(trade_id="1003", user_id=1, symbol="TSLA",  side="BUY", quantity=75,
                entry_price=175.80, mode="live", strategy_id="BREAKOUT",
                entry_time=_now - timedelta(hours=5),  exit_time=_now - timedelta(minutes=45),
                exit_price=169.40, order_state="FILLED", filled_quantity=75),
    TradeRecord(trade_id="1004", user_id=1, symbol="NFLX",  side="BUY", quantity=40,
                entry_price=634.00, mode="live", strategy_id="PULLBACK",
                entry_time=_now - timedelta(hours=3),  exit_time=_now - timedelta(minutes=30),
                exit_price=642.50, order_state="FILLED", filled_quantity=40),
    TradeRecord(trade_id="1005", user_id=1, symbol="CRM",   side="BUY", quantity=60,
                entry_price=305.00, mode="live", strategy_id="BREAKOUT",
                entry_time=_now - timedelta(hours=2),  exit_time=_now - timedelta(minutes=15),
                exit_price=298.00, order_state="FILLED", filled_quantity=60),
    # Bob
    TradeRecord(trade_id="2001", user_id=2, symbol="AAPL",  side="BUY", quantity=30,
                entry_price=178.00, mode="paper", strategy_id="BREAKOUT",
                entry_time=_now - timedelta(hours=8),  exit_time=_now - timedelta(hours=3),
                exit_price=185.50, order_state="FILLED", filled_quantity=30),
    TradeRecord(trade_id="2002", user_id=2, symbol="META",  side="BUY", quantity=20,
                entry_price=498.00, mode="paper", strategy_id="PULLBACK",
                entry_time=_now - timedelta(hours=5),  exit_time=_now - timedelta(hours=1),
                exit_price=489.00, order_state="FILLED", filled_quantity=20),
    # Carol
    TradeRecord(trade_id="3001", user_id=3, symbol="MSFT",  side="BUY", quantity=25,
                entry_price=408.00, mode="paper", strategy_id="BREAKOUT",
                entry_time=_now - timedelta(days=1),   exit_time=_now - timedelta(hours=5),
                exit_price=419.50, order_state="FILLED", filled_quantity=25),
    TradeRecord(trade_id="3002", user_id=3, symbol="NVDA",  side="BUY", quantity=15,
                entry_price=860.00, mode="paper", strategy_id="PULLBACK",
                entry_time=_now - timedelta(hours=4),  exit_time=_now - timedelta(hours=2),
                exit_price=872.00, order_state="FILLED", filled_quantity=15),
]

_SIGNALS: list[TradeSignal] = [
    TradeSignal(symbol="JPM", side="BUY", strategy_id="PULLBACK", score=71.9,
                entry_price=201.50, stop_loss=196.00, target_price=213.00, recommended_qty=50),
    TradeSignal(symbol="V",   side="BUY", strategy_id="BREAKOUT", score=68.5,
                entry_price=277.30, stop_loss=271.00, target_price=291.00, recommended_qty=35),
    TradeSignal(symbol="UNH", side="BUY", strategy_id="BREAKOUT", score=65.2,
                entry_price=525.00, stop_loss=514.00, target_price=548.00, recommended_qty=18),
]

_SCREENER_RESULTS_POOL: list[ScreenerResult] = [
    ScreenerResult("AAPL",  "Apple Inc.",            "Technology",   88.5, True,  True,  True,  True,  False),
    ScreenerResult("MSFT",  "Microsoft Corp.",        "Technology",   85.2, True,  True,  True,  False, True),
    ScreenerResult("NVDA",  "NVIDIA Corp.",           "Technology",   92.1, True,  True,  True,  True,  True),
    ScreenerResult("META",  "Meta Platforms",         "Technology",   79.4, False, True,  True,  True,  False),
    ScreenerResult("GOOGL", "Alphabet Inc.",          "Technology",   76.8, True,  True,  False, True,  False),
    ScreenerResult("AMZN",  "Amazon.com Inc.",        "Cons. Discr.", 74.3, True,  False, True,  False, True),
    ScreenerResult("JPM",   "JPMorgan Chase",         "Financials",   71.9, True,  True,  False, True,  False),
    ScreenerResult("V",     "Visa Inc.",              "Financials",   68.5, False, True,  True,  False, True),
    ScreenerResult("UNH",   "UnitedHealth Group",     "Healthcare",   65.2, True,  False, True,  True,  False),
    ScreenerResult("COST",  "Costco Wholesale",       "Cons. Stapl.", 62.7, True,  True,  False, False, True),
    ScreenerResult("HD",    "Home Depot Inc.",        "Cons. Discr.", 60.1, False, True,  True,  False, False),
    ScreenerResult("AMD",   "Advanced Micro Devices", "Technology",   57.8, True,  True,  False, True,  False),
]


# ── DemoService ────────────────────────────────────────────────────────────────

# Per-user equity allocations (demo)
_USER_EQUITY: dict[int, float] = {1: 150_000.0, 2: 80_000.0, 3: 50_000.0}


class DemoService(QObject):
    """Emits Qt signals when demo data changes — panels connect to these."""

    positions_updated  = pyqtSignal()          # position prices changed
    account_updated    = pyqtSignal()          # account state changed
    log_message        = pyqtSignal(str, str)  # (level, message)
    viewing_changed    = pyqtSignal()          # admin scope changed
    users_changed      = pyqtSignal()          # user list mutated
    feed_status_changed = pyqtSignal(str)      # 'disconnected' | 'connecting' | 'connected' | 'error'

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._positions  = [_copy_pos(p) for p in _POSITIONS]
        stored = load_users()
        if not stored:
            stored = list(_USERS)
            save_users(stored)
        self._users      = stored
        self._active_uid = self._users[0].user_id if self._users else 1
        self._viewing_uid: int | None = None   # None = aggregate all users
        self._feed_status: str = "disconnected"  # disconnected | connecting | connected | error
        self._system_cfg: SystemConfig = load_system_config()

        # Price drift simulation
        self._price_timer = QTimer(self)
        self._price_timer.timeout.connect(self._update_prices)
        self._price_timer.start(2_000)  # every 2 s

        # Demo log messages
        self._log_timer = QTimer(self)
        self._log_timer.timeout.connect(self._emit_demo_log)
        self._log_msgs = _DEMO_LOGS[:]
        self._log_idx  = 0
        self._log_timer.start(3_500)

    # ── Data accessors ─────────────────────────────────────────────────────────

    # ── Viewing context (admin scope) ──────────────────────────────────────────

    def set_viewing_uid(self, uid: int | None) -> None:
        """Switch admin scope. None = aggregate all users."""
        self._viewing_uid = uid
        self.viewing_changed.emit()
        self.positions_updated.emit()
        self.account_updated.emit()

    def get_viewing_uid(self) -> int | None:
        return self._viewing_uid

    def get_user_by_id(self, uid: int) -> UserProfile | None:
        return next((u for u in self._users if u.user_id == uid), None)

    def get_user_label(self) -> str:
        """Human-readable label for current scope."""
        if self._viewing_uid is None:
            return "All Users"
        u = self.get_user_by_id(self._viewing_uid)
        return u.username if u else "Unknown"

    # ── Data accessors ─────────────────────────────────────────────────────────

    def get_positions(self, user_id: int | None = None) -> list[OpenPosition]:
        """user_id=None → use viewing context (None=all, int=specific)."""
        uid = user_id if user_id is not None else self._viewing_uid
        if uid is None:
            return [p for p in self._positions if p.state != "CLOSED"]
        return [p for p in self._positions if p.user_id == uid and p.state != "CLOSED"]

    def get_all_trades(self, user_id: int | None = None) -> list[TradeRecord]:
        uid = user_id if user_id is not None else self._viewing_uid
        if uid is None:
            return list(_TRADES)
        return [t for t in _TRADES if t.user_id == uid]

    def get_account_state(self, user_id: int | None = None) -> AccountState:
        uid = user_id if user_id is not None else self._viewing_uid
        positions = self.get_positions(uid)
        open_val  = sum(p.position_value for p in positions)
        if uid is None:
            # Aggregate across all users
            equity   = sum(_USER_EQUITY.values())
            uid_out  = 0
        else:
            equity   = _USER_EQUITY.get(uid, 150_000.0)
            uid_out  = uid
        unrealised_pnl = sum(p.unrealised_pnl for p in positions)
        return AccountState(
            equity              = equity,
            start_of_day_equity = equity,
            open_position_value = open_val,
            user_id             = uid_out,
            daily_pnl           = unrealised_pnl,
        )

    def get_users(self) -> list[UserProfile]:
        return list(self._users)

    def get_active_user(self) -> UserProfile:
        return next(u for u in self._users if u.user_id == self._active_uid)

    def get_screener_results(self) -> list[ScreenerResult]:
        return sorted(_SCREENER_RESULTS_POOL, key=lambda r: r.composite_score, reverse=True)

    def get_pending_signals(self, user_id: int | None = None) -> list[TradeSignal]:
        return list(_SIGNALS)

    # ── Mutations (called from GUI actions) ────────────────────────────────────

    def close_position(self, symbol: str, user_id: int | None = None) -> None:
        uid = user_id if user_id is not None else self._active_uid
        for p in self._positions:
            if p.symbol == symbol and p.user_id == uid and p.quantity > 0:
                p.quantity = 0
                pnl = p.unrealised_pnl
                u = self.get_user_by_id(uid)
                uname = u.username if u else f"user#{uid}"
                self.log_message.emit(
                    "INFO",
                    f"[{uname}] Position closed: {symbol}  qty={p.quantity}  "
                    f"exit={p.current_price:.2f}  PnL={pnl:+.2f}",
                )
                self.positions_updated.emit()
                self.account_updated.emit()
                return

    def partial_close_position(self, symbol: str, qty: int, user_id: int | None = None) -> None:
        """Partially close a position by reducing quantity and booking partial PnL."""
        uid = user_id if user_id is not None else self._active_uid
        for p in self._positions:
            if p.symbol == symbol and p.user_id == uid and p.quantity > 0:
                qty = min(qty, p.quantity)
                pnl = (p.current_price - p.average_price) * qty
                p.quantity -= qty
                p.filled_quantity = p.quantity
                p.total_quantity  = p.quantity
                self.log_message.emit(
                    "INFO",
                    f"Partial close: {symbol}  closed={qty}  remaining={p.quantity}  "
                    f"exit={p.current_price:.2f}  PnL={pnl:+.2f}",
                )
                self.positions_updated.emit()
                self.account_updated.emit()
                return

    def set_stop_loss(self, symbol: str, price: float, user_id: int | None = None,
                      trailing: bool = False,
                      trail_by: str = "", trail_val: float = 0.0) -> None:
        """Update stop loss (fixed or trailing) for a position."""
        uid = user_id if user_id is not None else self._active_uid
        for p in self._positions:
            if p.symbol == symbol and p.user_id == uid and p.quantity > 0:
                old_sl = p.stop_loss
                p.stop_loss = price
                if trailing:
                    self.log_message.emit(
                        "INFO",
                        f"Trailing SL set: {symbol}  price={price:.2f}  "
                        f"trail_by='{trail_by}'  trail_val={trail_val}  "
                        f"(prev SL={old_sl:.2f})",
                    )
                else:
                    self.log_message.emit(
                        "INFO",
                        f"Stop loss updated: {symbol}  SL={price:.2f}  "
                        f"(prev SL={old_sl:.2f})",
                    )
                self.positions_updated.emit()
                return


    def execute_signal(self, signal: TradeSignal, quantity: int) -> int:
        """Simulate order submission.  Returns a demo order ID."""
        order_id = random.randint(10000, 99999)
        self.log_message.emit(
            "INFO",
            f"Order submitted: {signal.symbol}  side={signal.side}  "
            f"qty={quantity}  price={signal.entry_price:.2f}  "
            f"order_id={order_id}  mode={self.get_active_user().mode.upper()}",
        )
        return order_id

    # ── User CRUD mutations ────────────────────────────────────────────────────

    def add_user(self, profile: UserProfile) -> UserProfile:
        """Assign a new ID, persist, and emit users_changed."""
        new_profile = UserProfile(
            user_id         = next_user_id(self._users),
            username        = profile.username,
            display_name    = profile.display_name,
            ibkr_client_id  = profile.ibkr_client_id,
            mode            = profile.mode,
            risk_config     = profile.risk_config,
            strategy_config = profile.strategy_config,
            screener_config = profile.screener_config,
        )
        self._users.append(new_profile)
        save_users(self._users)
        self.users_changed.emit()
        return new_profile

    def update_user(self, profile: UserProfile) -> None:
        """Replace an existing user record in-place, persist, and emit users_changed."""
        for i, u in enumerate(self._users):
            if u.user_id == profile.user_id:
                self._users[i] = profile
                break
        save_users(self._users)
        self.users_changed.emit()

    def delete_user(self, user_id: int) -> str | None:
        """Delete a user by ID.  Returns an error string if blocked, None on success."""
        if user_id == self._active_uid:
            return "Cannot delete the active user."
        self._users = [u for u in self._users if u.user_id != user_id]
        save_users(self._users)
        self.users_changed.emit()
        return None

    # ── Feed / system config ───────────────────────────────────────────────────

    def get_feed_status(self) -> str:
        """Return current feed status string."""
        return self._feed_status

    def get_system_config(self) -> SystemConfig:
        return self._system_cfg

    def save_system_config(self, cfg: SystemConfig) -> None:
        """Persist system config and reload internal reference."""
        from us_swing.gui.system_store import save_system_config
        save_system_config(cfg)
        self._system_cfg = cfg
        self.log_message.emit("INFO", "System config saved.")

    def connect_feed(self) -> None:
        """Simulate connecting to the data feed (paper mode only)."""
        if self._feed_status == "connected":
            return
        self._feed_status = "connecting"
        self.feed_status_changed.emit(self._feed_status)
        self.log_message.emit(
            "INFO",
            f"[Feed] Connecting to {self._system_cfg.ibkr_host}:{self._system_cfg.ibkr_port} …",
        )
        # Simulate async handshake with a one-shot timer (1.5 s)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, self._on_feed_connected)

    def _on_feed_connected(self) -> None:
        self._feed_status = "connected"
        self.feed_status_changed.emit(self._feed_status)
        self.log_message.emit("INFO", "[Feed] Data feed connected — paper mode active.")

    def disconnect_feed(self) -> None:
        """Disconnect the data feed."""
        self._feed_status = "disconnected"
        self.feed_status_changed.emit(self._feed_status)
        self.log_message.emit("INFO", "[Feed] Data feed disconnected.")

    # ── Internal ───────────────────────────────────────────────────────────────

    def _update_prices(self) -> None:
        changed = False
        for pos in self._positions:
            if pos.quantity <= 0:
                continue
            pct = random.gauss(0, 0.003)   # ±0.3% std per tick
            pos.current_price = round(pos.current_price * (1 + pct), 2)
            changed = True
        if changed:
            self.positions_updated.emit()
            self.account_updated.emit()

    def _emit_demo_log(self) -> None:
        if self._log_msgs:
            level, msg = self._log_msgs[self._log_idx % len(self._log_msgs)]
            self.log_message.emit(level, msg)
            self._log_idx += 1


_DEMO_LOGS: list[tuple[str, str]] = [
    ("INFO",    "StrategyEngine: BREAKOUT signal evaluated for AAPL — entry conditions met"),
    ("INFO",    "PacingQueue: 3 requests dispatched (window: 47/50)"),
    ("INFO",    "DailyPnLTracker: running total = +$1,576.00"),
    ("WARNING", "PositionTracker: MSFT partial fill — 100/150 filled"),
    ("INFO",    "ScreenerEngine: universe scan complete — 503 symbols evaluated"),
    ("INFO",    "IBKRClient: connection stable — latency 12ms"),
    ("INFO",    "StrategyEngine: PULLBACK signal evaluated for V — entry conditions met"),
    ("INFO",    "DataEngine: AAPL price updated — $187.30"),
    ("WARNING", "RiskManager: GOOGL position approaching stop-loss ($176.50 vs $172.00)"),
    ("INFO",    "HealthMonitor: all systems nominal"),
    ("ERROR",   "IBKRClient: historical data error 162 for XYZ — retry queued"),
    ("INFO",    "HistoricalDataEngine: COST bootstrap complete — 252 daily bars loaded"),
]


def _copy_pos(p: OpenPosition) -> OpenPosition:
    """Return a shallow copy so demo mutations don't affect the seed."""
    return OpenPosition(
        symbol=p.symbol, user_id=p.user_id, quantity=p.quantity,
        filled_quantity=p.filled_quantity, total_quantity=p.total_quantity,
        average_price=p.average_price, current_price=p.current_price,
        stop_loss=p.stop_loss, target_price=p.target_price,
        strategy_id=p.strategy_id, entry_time=p.entry_time,
        state=p.state, mode=p.mode,
    )
