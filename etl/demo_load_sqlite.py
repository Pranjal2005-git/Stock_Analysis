"""
SANDBOX-ONLY DEMO LOADER.

This is a stdlib-only (sqlite3) re-implementation of etl/load.py, used
solely to demonstrate the pipeline end-to-end in environments where pip
can't install SQLAlchemy/psycopg2 (e.g. an offline sandbox). It targets
the exact same schema as sql/schema.sql (SQLite-flavored DDL) and is NOT
part of the real project deliverable -- on a normal machine with
internet access, use `python run_pipeline.py` (which calls etl/load.py,
the SQLAlchemy version that also supports real PostgreSQL).

Run directly: python -m etl.demo_load_sqlite
"""
from __future__ import annotations

import sqlite3
import pandas as pd

from etl.utils import load_config, get_logger, resolve_path

log = get_logger("demo_load_sqlite")

SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS dim_ticker (
    ticker_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL UNIQUE,
    company_name TEXT,
    sector TEXT
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_date TEXT NOT NULL UNIQUE,
    day_of_week TEXT,
    month INTEGER,
    quarter INTEGER,
    year INTEGER,
    is_trading_day INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS fact_prices (
    price_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_id INTEGER NOT NULL REFERENCES dim_date(date_id),
    ticker_id INTEGER NOT NULL REFERENCES dim_ticker(ticker_id),
    open REAL, high REAL, low REAL, close REAL, volume INTEGER,
    UNIQUE(date_id, ticker_id)
);

CREATE TABLE IF NOT EXISTS fact_indicators (
    indicator_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_id INTEGER NOT NULL REFERENCES dim_date(date_id),
    ticker_id INTEGER NOT NULL REFERENCES dim_ticker(ticker_id),
    daily_return REAL, sma_20 REAL, sma_50 REAL, sma_200 REAL,
    ema_12 REAL, ema_26 REAL, rsi_14 REAL, macd REAL, macd_signal REAL,
    bb_upper REAL, bb_lower REAL, volatility_20d REAL,
    UNIQUE(date_id, ticker_id)
);

CREATE INDEX IF NOT EXISTS idx_fact_prices_ticker_date ON fact_prices (ticker_id, date_id);
CREATE INDEX IF NOT EXISTS idx_fact_indicators_ticker_date ON fact_indicators (ticker_id, date_id);
"""

SECTOR_LOOKUP = {
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Communication Services",
    "AMZN": "Consumer Discretionary", "NVDA": "Technology",
}


def run(config_path: str = None) -> dict:
    cfg = load_config(config_path)
    processed_dir = resolve_path(cfg["paths"]["processed_dir"])
    combined_path = processed_dir / "all_tickers_features.csv"
    if not combined_path.exists():
        raise FileNotFoundError(f"{combined_path} not found. Run etl.clean and etl.features first.")

    df = pd.read_csv(combined_path, parse_dates=["Date"])
    db_path = resolve_path(cfg["database"]["sqlite_path"])

    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQLITE)

    for ticker in sorted(df["ticker"].unique()):
        conn.execute(
            """INSERT INTO dim_ticker (ticker, company_name, sector) VALUES (?, ?, ?)
               ON CONFLICT(ticker) DO UPDATE SET sector=excluded.sector""",
            (ticker, ticker, SECTOR_LOOKUP.get(ticker, "Unknown")),
        )

    for d in pd.to_datetime(df["Date"].unique()):
        conn.execute(
            """INSERT INTO dim_date (full_date, day_of_week, month, quarter, year, is_trading_day)
               VALUES (?, ?, ?, ?, ?, 1)
               ON CONFLICT(full_date) DO NOTHING""",
            (d.date().isoformat(), d.strftime("%A"), d.month, (d.month - 1) // 3 + 1, d.year),
        )
    conn.commit()

    ticker_ids = dict(conn.execute("SELECT ticker, ticker_id FROM dim_ticker").fetchall())
    date_ids = dict(conn.execute("SELECT full_date, date_id FROM dim_date").fetchall())

    def clean_num(v):
        try:
            return None if pd.isna(v) else float(v)
        except (TypeError, ValueError):
            return None

    n_prices, n_indicators = 0, 0
    for _, r in df.iterrows():
        date_id = date_ids[r["Date"].date().isoformat()]
        ticker_id = ticker_ids[r["ticker"]]

        conn.execute("""
            INSERT INTO fact_prices (date_id, ticker_id, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date_id, ticker_id) DO UPDATE SET
                open=excluded.open, high=excluded.high, low=excluded.low,
                close=excluded.close, volume=excluded.volume
        """, (date_id, ticker_id, clean_num(r.get("Open")), clean_num(r.get("High")),
              clean_num(r.get("Low")), clean_num(r.get("Close")), clean_num(r.get("Volume"))))
        n_prices += 1

        conn.execute("""
            INSERT INTO fact_indicators (date_id, ticker_id, daily_return, sma_20, sma_50, sma_200,
                ema_12, ema_26, rsi_14, macd, macd_signal, bb_upper, bb_lower, volatility_20d)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date_id, ticker_id) DO UPDATE SET
                daily_return=excluded.daily_return, sma_20=excluded.sma_20, sma_50=excluded.sma_50,
                sma_200=excluded.sma_200, ema_12=excluded.ema_12, ema_26=excluded.ema_26,
                rsi_14=excluded.rsi_14, macd=excluded.macd, macd_signal=excluded.macd_signal,
                bb_upper=excluded.bb_upper, bb_lower=excluded.bb_lower,
                volatility_20d=excluded.volatility_20d
        """, (date_id, ticker_id, clean_num(r.get("daily_return")), clean_num(r.get("sma_20")),
              clean_num(r.get("sma_50")), clean_num(r.get("sma_200")), clean_num(r.get("ema_12")),
              clean_num(r.get("ema_26")), clean_num(r.get("rsi_14")), clean_num(r.get("macd")),
              clean_num(r.get("macd_signal")), clean_num(r.get("bb_upper")), clean_num(r.get("bb_lower")),
              clean_num(r.get("volatility_20d"))))
        n_indicators += 1

    conn.commit()
    conn.close()
    log.info(f"Demo load complete: {n_prices} price rows, {n_indicators} indicator rows -> {db_path}")
    return {"prices_upserted": n_prices, "indicators_upserted": n_indicators}


if __name__ == "__main__":
    run()
