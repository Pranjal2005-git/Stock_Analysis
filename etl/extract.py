"""
Phase 2 - Data Acquisition (Extract)

Pulls historical daily OHLCV data for every ticker in config.yaml from
Yahoo Finance and writes one timestamped CSV per ticker into data/raw/.

Run directly:  python -m etl.extract
Requires internet access + `yfinance` installed (see requirements.txt).

If yfinance or network access isn't available (e.g. an offline sandbox),
use etl/demo_data.py instead -- it generates synthetic OHLCV data in the
exact same raw format so the rest of the pipeline (clean -> features ->
load) can be developed and tested without a live connection.
"""
from __future__ import annotations

import time
from datetime import datetime, date

import pandas as pd

from etl.utils import load_config, get_logger, resolve_path

log = get_logger("extract")

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5


def fetch_ticker(ticker: str, start: str, end: str | None, retries: int = MAX_RETRIES) -> pd.DataFrame:
    """Fetch OHLCV history for one ticker with retry/backoff on failure."""
    try:
        import yfinance as yf
    except ImportError as e:
        raise RuntimeError(
            "yfinance is not installed. Run `pip install -r requirements.txt`, "
            "or use etl/demo_data.py for an offline synthetic dataset."
        ) from e

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            log.info(f"Fetching {ticker} (attempt {attempt}/{retries})...")
            df = yf.Ticker(ticker).history(start=start, end=end, interval="1d")
            if df.empty:
                raise ValueError(f"No data returned for {ticker}")
            df = df.reset_index()
            df["ticker"] = ticker
            return df
        except Exception as e:  # noqa: BLE001 - we want to retry on anything transient
            last_error = e
            log.warning(f"{ticker}: attempt {attempt} failed ({e}); backing off {RETRY_BACKOFF_SECONDS}s")
            time.sleep(RETRY_BACKOFF_SECONDS)

    raise RuntimeError(f"Failed to fetch {ticker} after {retries} attempts") from last_error


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
        df = fetch_ticker(ticker, start, end)
        out_path = raw_dir / f"{ticker}_{run_stamp}.csv"
        df.to_csv(out_path, index=False)
        log.info(f"{ticker}: wrote {len(df)} rows -> {out_path.name} "
                  f"(range {df['Date'].min().date()} to {df['Date'].max().date()})")
        written_files.append(str(out_path))

    log.info(f"Extraction complete. {len(written_files)} files written to {raw_dir}")
    return written_files


if __name__ == "__main__":
    run()
