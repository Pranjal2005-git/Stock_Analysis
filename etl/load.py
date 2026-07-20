"""
Phase 6 - ETL Pipeline Automation (Load)

Reads data/processed/all_tickers_features.csv and upserts it into
dim_ticker, dim_date, fact_prices, and fact_indicators. Idempotent: running
this repeatedly with overlapping data updates existing rows instead of
duplicating them (keyed on ticker / full_date via unique constraints).

Run directly: python -m etl.load
"""
from __future__ import annotations

import math

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from etl.db import get_engine, init_db, dim_ticker, dim_date, fact_prices, fact_indicators
from etl.utils import load_config, get_logger, resolve_path

log = get_logger("load")

SECTOR_LOOKUP = {
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Communication Services",
    "AMZN": "Consumer Discretionary", "NVDA": "Technology",
}


def _upsert(conn, table, rows: list[dict], conflict_cols: list[str]) -> tuple[int, int]:
    """Insert rows, updating on conflict. Works for both postgres and sqlite
    dialects via SQLAlchemy's dialect-specific insert().on_conflict_do_update."""
    if not rows:
        return 0, 0

    is_sqlite = conn.engine.dialect.name == "sqlite"
    insert_fn = sqlite_insert if is_sqlite else pg_insert

    inserted_or_updated = 0
    for row in rows:
        stmt = insert_fn(table).values(**row)
        update_cols = {c: getattr(stmt.excluded, c) for c in row if c not in conflict_cols}
        stmt = stmt.on_conflict_do_update(index_elements=conflict_cols, set_=update_cols)
        conn.execute(stmt)
        inserted_or_updated += 1
    return inserted_or_updated, 0


def upsert_dim_ticker(conn, tickers: list[str]) -> dict[str, int]:
    rows = [{"ticker": t, "company_name": t, "sector": SECTOR_LOOKUP.get(t, "Unknown")} for t in tickers]
    _upsert(conn, dim_ticker, rows, conflict_cols=["ticker"])
    result = conn.execute(select(dim_ticker.c.ticker, dim_ticker.c.ticker_id))
    return {r.ticker: r.ticker_id for r in result}


def upsert_dim_date(conn, dates: pd.Series) -> dict[str, int]:
    unique_dates = pd.to_datetime(dates.unique())
    rows = []
    for d in unique_dates:
        rows.append({
            "full_date": d.date(),
            "day_of_week": d.strftime("%A"),
            "month": d.month,
            "quarter": (d.month - 1) // 3 + 1,
            "year": d.year,
            "is_trading_day": True,
        })
    _upsert(conn, dim_date, rows, conflict_cols=["full_date"])
    result = conn.execute(select(dim_date.c.full_date, dim_date.c.date_id))
    return {str(r.full_date): r.date_id for r in result}


def _clean_num(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return v


def run(config_path: str = None) -> dict:
    cfg = load_config(config_path)
    processed_dir = resolve_path(cfg["paths"]["processed_dir"])
    combined_path = processed_dir / "all_tickers_features.csv"
    if not combined_path.exists():
        raise FileNotFoundError(
            f"{combined_path} not found. Run `python -m etl.features` first."
        )

    df = pd.read_csv(combined_path, parse_dates=["Date"])
    engine = get_engine(config_path)
    init_db(engine)

    stats = {"prices_upserted": 0, "indicators_upserted": 0}

    with engine.begin() as conn:
        ticker_ids = upsert_dim_ticker(conn, sorted(df["ticker"].unique().tolist()))
        date_ids = upsert_dim_date(conn, df["Date"])

        price_rows, indicator_rows = [], []
        for _, r in df.iterrows():
            date_id = date_ids[str(r["Date"].date())]
            ticker_id = ticker_ids[r["ticker"]]

            price_rows.append({
                "date_id": date_id, "ticker_id": ticker_id,
                "open": _clean_num(r.get("Open")), "high": _clean_num(r.get("High")),
                "low": _clean_num(r.get("Low")), "close": _clean_num(r.get("Close")),
                "volume": _clean_num(r.get("Volume")),
            })
            indicator_rows.append({
                "date_id": date_id, "ticker_id": ticker_id,
                "daily_return": _clean_num(r.get("daily_return")),
                "sma_20": _clean_num(r.get("sma_20")), "sma_50": _clean_num(r.get("sma_50")),
                "sma_200": _clean_num(r.get("sma_200")),
                "ema_12": _clean_num(r.get("ema_12")), "ema_26": _clean_num(r.get("ema_26")),
                "rsi_14": _clean_num(r.get("rsi_14")),
                "macd": _clean_num(r.get("macd")), "macd_signal": _clean_num(r.get("macd_signal")),
                "bb_upper": _clean_num(r.get("bb_upper")), "bb_lower": _clean_num(r.get("bb_lower")),
                "volatility_20d": _clean_num(r.get("volatility_20d")),
            })

        n_p, _ = _upsert(conn, fact_prices, price_rows, conflict_cols=["date_id", "ticker_id"])
        n_i, _ = _upsert(conn, fact_indicators, indicator_rows, conflict_cols=["date_id", "ticker_id"])
        stats["prices_upserted"] = n_p
        stats["indicators_upserted"] = n_i

    log.info(f"Load complete: {stats['prices_upserted']} price rows, "
             f"{stats['indicators_upserted']} indicator rows upserted "
             f"into {'PostgreSQL' if cfg['database']['target']=='postgresql' else 'SQLite'} "
             f"across {len(ticker_ids)} tickers and {len(date_ids)} dates.")
    return stats


if __name__ == "__main__":
    run()
