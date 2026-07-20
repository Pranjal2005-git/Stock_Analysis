"""
Offline synthetic data generator.

This is NOT a replacement for etl/extract.py -- it exists so the rest of
the pipeline (clean -> features -> load -> SQL -> dashboard) can be built,
tested, and demoed in environments without live internet access (e.g. CI,
or an offline sandbox). It writes CSVs into data/raw/ in the exact same
shape that etl/extract.py produces (Date, Open, High, Low, Close, Volume,
ticker), so nothing downstream needs to know the difference.

Prices are generated with a seeded geometric random walk with drift, so
each ticker gets a distinct, reproducible, realistic-looking price
history -- but this is demo data, not real market history.

Run directly: python -m etl.demo_data
"""
from __future__ import annotations

from datetime import datetime, date

import numpy as np
import pandas as pd

from etl.utils import load_config, get_logger, resolve_path

log = get_logger("demo_data")

# Rough starting price + annualized drift/volatility per ticker, chosen to
# be broadly plausible for these five names -- not real quotes.
TICKER_PROFILES = {
    "AAPL":  {"start_price": 40.0,  "annual_drift": 0.24, "annual_vol": 0.30, "seed": 1},
    "MSFT":  {"start_price": 100.0, "annual_drift": 0.22, "annual_vol": 0.27, "seed": 2},
    "GOOGL": {"start_price": 55.0,  "annual_drift": 0.18, "annual_vol": 0.29, "seed": 3},
    "AMZN":  {"start_price": 75.0,  "annual_drift": 0.20, "annual_vol": 0.34, "seed": 4},
    "NVDA":  {"start_price": 4.0,   "annual_drift": 0.55, "annual_vol": 0.48, "seed": 5},
}


def generate_ticker_history(ticker: str, start: str, end: str) -> pd.DataFrame:
    profile = TICKER_PROFILES.get(ticker, {"start_price": 50.0, "annual_drift": 0.15, "annual_vol": 0.30, "seed": 42})
    rng = np.random.default_rng(profile["seed"])

    dates = pd.bdate_range(start=start, end=end)  # business days only, like real trading days
    n = len(dates)

    daily_drift = profile["annual_drift"] / 252
    daily_vol = profile["annual_vol"] / np.sqrt(252)

    # Geometric Brownian motion for the close price
    shocks = rng.normal(loc=daily_drift, scale=daily_vol, size=n)
    log_prices = np.log(profile["start_price"]) + np.cumsum(shocks)
    close = np.exp(log_prices)

    # Derive open/high/low from close with small intraday noise
    intraday_noise = rng.normal(loc=0, scale=daily_vol * 0.5, size=n)
    open_ = close * (1 + intraday_noise)
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, daily_vol * 0.4, size=n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, daily_vol * 0.4, size=n)))
    volume = rng.integers(low=int(2e6), high=int(9e7), size=n)

    df = pd.DataFrame({
        "Date": dates,
        "Open": open_.round(2),
        "High": high.round(2),
        "Low": low.round(2),
        "Close": close.round(2),
        "Volume": volume,
        "ticker": ticker,
    })
    return df


def run(config_path: str = None) -> list[str]:
    cfg = load_config(config_path)
    tickers = cfg["tickers"]
    start = cfg["history"]["start_date"]
    end = cfg["history"]["end_date"] or date.today().isoformat()
    raw_dir = resolve_path(cfg["paths"]["raw_dir"])
    raw_dir.mkdir(parents=True, exist_ok=True)

    run_stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    written_files = []

    for ticker in tickers:
        df = generate_ticker_history(ticker, start, end)
        out_path = raw_dir / f"{ticker}_{run_stamp}.csv"
        df.to_csv(out_path, index=False)
        log.info(f"{ticker}: generated {len(df)} synthetic rows -> {out_path.name}")
        written_files.append(str(out_path))

    log.info(f"Synthetic extraction complete. {len(written_files)} files written to {raw_dir}")
    return written_files


if __name__ == "__main__":
    run()
