"""
Phase 5/6 - Database layer.

Table definitions here are the SQLAlchemy mirror of sql/schema.sql (the
hand-written, canonical PostgreSQL DDL). Defining them in SQLAlchemy Core
as well lets load.py create/upsert against either PostgreSQL (production)
or SQLite (zero-setup local dev/demo) with the same code path -- only the
engine URL changes.

For real Postgres, set DATABASE_URL in .env and config.yaml -> database.target
to "postgresql". For local demo/dev, target "sqlite" needs no setup at all.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, Date, Numeric,
    BigInteger, ForeignKey, UniqueConstraint, Engine,
)

from etl.utils import load_config, resolve_path

load_dotenv()

metadata = MetaData()

dim_ticker = Table(
    "dim_ticker", metadata,
    Column("ticker_id", Integer, primary_key=True, autoincrement=True),
    Column("ticker", String(10), nullable=False, unique=True),
    Column("company_name", String(100)),
    Column("sector", String(50)),
)

dim_date = Table(
    "dim_date", metadata,
    Column("date_id", Integer, primary_key=True, autoincrement=True),
    Column("full_date", Date, nullable=False, unique=True),
    Column("day_of_week", String(10)),
    Column("month", Integer),
    Column("quarter", Integer),
    Column("year", Integer),
    Column("is_trading_day", Integer),  # 1/0 (boolean, portable across sqlite/postgres)
)

fact_prices = Table(
    "fact_prices", metadata,
    Column("price_id", Integer, primary_key=True, autoincrement=True),
    Column("date_id", Integer, ForeignKey("dim_date.date_id"), nullable=False),
    Column("ticker_id", Integer, ForeignKey("dim_ticker.ticker_id"), nullable=False),
    Column("open", Numeric(12, 4)),
    Column("high", Numeric(12, 4)),
    Column("low", Numeric(12, 4)),
    Column("close", Numeric(12, 4)),
    Column("volume", BigInteger),
    UniqueConstraint("date_id", "ticker_id", name="uq_fact_prices_date_ticker"),
)

fact_indicators = Table(
    "fact_indicators", metadata,
    Column("indicator_id", Integer, primary_key=True, autoincrement=True),
    Column("date_id", Integer, ForeignKey("dim_date.date_id"), nullable=False),
    Column("ticker_id", Integer, ForeignKey("dim_ticker.ticker_id"), nullable=False),
    Column("daily_return", Numeric(12, 6)),
    Column("sma_20", Numeric(12, 4)),
    Column("sma_50", Numeric(12, 4)),
    Column("sma_200", Numeric(12, 4)),
    Column("ema_12", Numeric(12, 4)),
    Column("ema_26", Numeric(12, 4)),
    Column("rsi_14", Numeric(6, 2)),
    Column("macd", Numeric(12, 6)),
    Column("macd_signal", Numeric(12, 6)),
    Column("bb_upper", Numeric(12, 4)),
    Column("bb_lower", Numeric(12, 4)),
    Column("volatility_20d", Numeric(12, 6)),
    UniqueConstraint("date_id", "ticker_id", name="uq_fact_indicators_date_ticker"),
)


def get_engine(config_path: str = None) -> Engine:
    cfg = load_config(config_path)
    db_cfg = cfg["database"]

    if db_cfg["target"] == "postgresql":
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL not set in .env for postgresql target")
        return create_engine(url)

    # sqlite fallback -- zero setup, file lives at project root
    sqlite_path = resolve_path(db_cfg["sqlite_path"])
    return create_engine(f"sqlite:///{sqlite_path}")


def init_db(engine: Engine) -> None:
    metadata.create_all(engine)
