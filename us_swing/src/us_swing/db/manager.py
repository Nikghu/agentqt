"""Module: MD-INF-004.001.M01 — db/manager.py
Parent SRD: SRD-INF-004.001 – SRD-INF-004.006, SRD-INF-006.001 – SRD-INF-006.005

Backend-agnostic repository layer built on SQLAlchemy Core.
All public methods are synchronous and thread-safe (each call opens and
closes its own connection from the engine pool).

Supported backends: SQLite (dev) · PostgreSQL (prod) — selected via
``DatabaseConfig.url``.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

import sqlalchemy as sa

from us_swing.data.models import (
    OHLCVBar,
    PositionRecord,
    TradeRecord,
    UniverseRecord,
    UserRecord,
)
from us_swing.db.schema import (
    PRICE_TABLES,
    create_schema,
    drop_schema,
    positions,
    trades,
    universe,
    users,
    watchlist,
)
from us_swing.exceptions import ConfigurationError, DatabaseError

log = logging.getLogger(__name__)

_SUPPORTED_SCHEMES = {"sqlite", "postgresql", "postgresql+psycopg2", "postgresql+asyncpg"}

# ISO 8601 UTC format used for all datetime strings in the DB.
_DT_FORMAT = "%Y-%m-%dT%H:%M:%S"


def _dt_to_str(dt: datetime) -> str:
    return dt.strftime(_DT_FORMAT)


def _str_to_dt(s: str) -> datetime:
    return datetime.strptime(s, _DT_FORMAT).replace(tzinfo=timezone.utc)


class DatabaseManager:
    """Single entry-point for all database operations.

    Usage::

        db = DatabaseManager("sqlite:///./data/us_swing.db")
        db.create_schema()
    """

    def __init__(self, database_url: str) -> None:
        scheme = database_url.split("://")[0]
        if scheme not in _SUPPORTED_SCHEMES:
            raise ConfigurationError(
                f"Unsupported database backend '{scheme}'. "
                f"Supported: {_SUPPORTED_SCHEMES}"
            )
        # SQLite needs connect_args to allow cross-thread usage.
        connect_args: dict[str, Any] = {}
        if scheme == "sqlite":
            connect_args["check_same_thread"] = False

        self._engine = sa.create_engine(
            database_url,
            connect_args=connect_args,
            future=True,
        )
        log.info("DatabaseManager initialised: %s", database_url)

    # ── Schema ────────────────────────────────────────────────────────────────

    def create_schema(self) -> None:
        create_schema(self._engine)
        log.info("Schema created / verified OK")

    def drop_schema(self) -> None:
        """Drop all tables.  Test use only — irreversible."""
        drop_schema(self._engine)

    # ── OHLCV bars ────────────────────────────────────────────────────────────

    # SQLite caps bound variables per statement at 999; with 7 columns per bar row
    # that allows at most 142 rows per execute. Use 100 for a safe margin.
    _INSERT_BATCH = 100

    def insert_bars(self, symbol: str, timeframe: str, bars: list[OHLCVBar]) -> int:
        """Bulk-insert bars in batches; silently skips duplicates.

        Returns:
            Number of rows actually inserted.
        """
        if not bars:
            return 0
        table = self._price_table(timeframe)
        rows = [
            {
                "symbol":   symbol,
                "datetime": _dt_to_str(b.datetime),
                "open":     b.open,
                "high":     b.high,
                "low":      b.low,
                "close":    b.close,
                "volume":   b.volume,
            }
            for b in bars
        ]
        inserted = 0
        with self._engine.begin() as conn:
            for i in range(0, len(rows), self._INSERT_BATCH):
                chunk = rows[i : i + self._INSERT_BATCH]
                stmt = sa.dialects.sqlite.insert(table).values(chunk).on_conflict_do_nothing()  # type: ignore[attr-defined]
                result = conn.execute(stmt)
                inserted += result.rowcount if result.rowcount != -1 else len(chunk)

        if inserted < len(rows):
            log.debug(
                "insert_bars(%s, %s): %d new, %d duplicates skipped",
                symbol, timeframe, inserted, len(rows) - inserted,
            )
        return inserted

    def fetch_bars(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[OHLCVBar]:
        """Return bars in [start, end] inclusive, ordered by datetime."""
        table = self._price_table(timeframe)
        stmt = (
            sa.select(table)
            .where(
                table.c.symbol   == symbol,
                table.c.datetime >= _dt_to_str(start),
                table.c.datetime <= _dt_to_str(end),
            )
            .order_by(table.c.datetime)
        )
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [
            OHLCVBar(
                symbol=symbol,
                datetime=_str_to_dt(r["datetime"]),
                open=r["open"],
                high=r["high"],
                low=r["low"],
                close=r["close"],
                volume=r["volume"],
                timeframe=timeframe,
            )
            for r in rows
        ]

    def get_last_timestamp(self, symbol: str, timeframe: str) -> datetime | None:
        """Return the latest stored datetime for (symbol, timeframe), or None."""
        table = self._price_table(timeframe)
        stmt = sa.select(sa.func.max(table.c.datetime)).where(table.c.symbol == symbol)
        with self._engine.connect() as conn:
            result = conn.execute(stmt).scalar()
        return _str_to_dt(result) if result else None

    def get_first_timestamp(self, symbol: str, timeframe: str) -> datetime | None:
        """Return the earliest stored datetime for (symbol, timeframe), or None."""
        table = self._price_table(timeframe)
        stmt = sa.select(sa.func.min(table.c.datetime)).where(table.c.symbol == symbol)
        with self._engine.connect() as conn:
            result = conn.execute(stmt).scalar()
        return _str_to_dt(result) if result else None

    # ── Universe ──────────────────────────────────────────────────────────────

    def upsert_universe(self, records: list[UniverseRecord]) -> None:
        """Insert-or-update universe records by symbol."""
        if not records:
            return
        rows = [{"symbol": r.symbol, "name": r.name, "sector": r.sector} for r in records]
        with self._engine.begin() as conn:
            ins = sa.dialects.sqlite.insert(universe).values(rows)  # type: ignore[attr-defined]
            stmt = ins.on_conflict_do_update(
                index_elements=["symbol"],
                set_={"name": ins.excluded.name, "sector": ins.excluded.sector},
            )
            conn.execute(stmt)
        log.debug("upsert_universe: %d records", len(records))

    def fetch_universe(self) -> list[UniverseRecord]:
        with self._engine.connect() as conn:
            rows = conn.execute(sa.select(universe)).mappings().all()
        return [UniverseRecord(symbol=r["symbol"], name=r["name"], sector=r["sector"]) for r in rows]

    # ── Watchlist ─────────────────────────────────────────────────────────────

    def upsert_watchlist(self, symbols: list[str], dt: date) -> None:
        date_str = dt.isoformat()
        rows = [{"date": date_str, "symbol": s} for s in symbols]
        with self._engine.begin() as conn:
            stmt = sa.dialects.sqlite.insert(watchlist).values(rows).on_conflict_do_nothing()  # type: ignore[attr-defined]
            conn.execute(stmt)

    def fetch_watchlist(self, dt: date) -> list[str]:
        stmt = sa.select(watchlist.c.symbol).where(watchlist.c.date == dt.isoformat())
        with self._engine.connect() as conn:
            return [r[0] for r in conn.execute(stmt)]

    # ── Trades ────────────────────────────────────────────────────────────────

    def insert_trade(self, trade: TradeRecord) -> None:
        row: dict[str, Any] = {
            "trade_id":    trade.trade_id,
            "user_id":     trade.user_id,
            "symbol":      trade.symbol,
            "side":        trade.side,
            "entry_time":  _dt_to_str(trade.entry_time),
            "entry_price": trade.entry_price,
            "exit_time":   _dt_to_str(trade.exit_time) if trade.exit_time else None,
            "exit_price":  trade.exit_price,
            "quantity":    trade.quantity,
            "pnl":         trade.pnl,
            "strategy_id": trade.strategy_id,
            "mode":        trade.mode,
            "status":      trade.status,
        }
        with self._engine.begin() as conn:
            conn.execute(trades.insert().values(**row))

    def update_trade_exit(
        self,
        trade_id: str,
        exit_time: datetime,
        exit_price: float,
        pnl: float,
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                trades.update()
                .where(trades.c.trade_id == trade_id)
                .values(
                    exit_time=_dt_to_str(exit_time),
                    exit_price=exit_price,
                    pnl=pnl,
                    status="CLOSED",
                )
            )

    # ── Positions ─────────────────────────────────────────────────────────────

    def upsert_position(self, pos: PositionRecord) -> None:
        row = {
            "symbol":        pos.symbol,
            "user_id":       pos.user_id,
            "quantity":      pos.quantity,
            "average_price": pos.average_price,
            "stop_loss":     pos.stop_loss,
            "target_price":  pos.target_price,
            "trailing_stop": pos.trailing_stop,
            "mode":          pos.mode,
            "state":         pos.state,
        }
        with self._engine.begin() as conn:
            stmt = sa.dialects.sqlite.insert(positions).values(**row).on_conflict_do_update(  # type: ignore[attr-defined]
                index_elements=["user_id", "symbol"],
                set_={k: v for k, v in row.items() if k not in ("user_id", "symbol")},
            )
            conn.execute(stmt)

    def delete_position(self, user_id: int, symbol: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                positions.delete().where(
                    positions.c.user_id == user_id,
                    positions.c.symbol  == symbol,
                )
            )

    def fetch_open_positions(self, user_id: int) -> list[PositionRecord]:
        stmt = sa.select(positions).where(
            positions.c.user_id == user_id,
            positions.c.state   != "CLOSED",
        )
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [
            PositionRecord(
                symbol        = r["symbol"],
                user_id       = r["user_id"],
                quantity      = r["quantity"],
                average_price = r["average_price"],
                stop_loss     = r["stop_loss"],
                target_price  = r["target_price"],
                trailing_stop = r["trailing_stop"],
                mode          = r["mode"],
                state         = r["state"],
            )
            for r in rows
        ]

    # ── Users ─────────────────────────────────────────────────────────────────

    def insert_user(self, user: UserRecord) -> int:
        """Insert a new user row and return the auto-generated user_id."""
        row = {
            "username":       user.username,
            "display_name":   user.display_name,
            "ibkr_client_id": user.ibkr_client_id,
            "settings_json":  user.settings_json,
            "mode":           user.mode,
        }
        with self._engine.begin() as conn:
            result = conn.execute(users.insert().values(**row))
            return int(result.inserted_primary_key[0])

    def fetch_user(self, user_id: int) -> UserRecord | None:
        stmt = sa.select(users).where(users.c.user_id == user_id)
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        if row is None:
            return None
        return self._row_to_user_record(row)

    def update_user(self, user_id: int, **fields: Any) -> None:
        allowed = {"username", "display_name", "ibkr_client_id", "settings_json", "mode"}
        update_vals = {k: v for k, v in fields.items() if k in allowed}
        if not update_vals:
            return
        with self._engine.begin() as conn:
            conn.execute(
                users.update()
                .where(users.c.user_id == user_id)
                .values(**update_vals)
            )

    def delete_user(self, user_id: int) -> None:
        # Orphan trades / positions are intentionally retained (audit trail).
        with self._engine.begin() as conn:
            conn.execute(users.delete().where(users.c.user_id == user_id))

    def fetch_all_users(self) -> list[UserRecord]:
        with self._engine.connect() as conn:
            rows = conn.execute(sa.select(users)).mappings().all()
        return [self._row_to_user_record(r) for r in rows]

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _price_table(timeframe: str) -> sa.Table:
        try:
            return PRICE_TABLES[timeframe]
        except KeyError:
            raise DatabaseError(
                f"Unknown timeframe '{timeframe}'. "
                f"Supported: {list(PRICE_TABLES)}"
            )

    @staticmethod
    def _row_to_user_record(r: Any) -> UserRecord:
        return UserRecord(
            user_id        = r["user_id"],
            username       = r["username"],
            display_name   = r["display_name"],
            ibkr_client_id = r["ibkr_client_id"],
            settings_json  = r["settings_json"] or "{}",
            mode           = r["mode"],
        )
