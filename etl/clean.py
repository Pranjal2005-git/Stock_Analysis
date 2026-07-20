"""
Phase 3 - Data Cleaning & Validation

Reads every raw CSV in data/raw/, enforces types, handles missing/duplicate
rows, flags outlier price moves, and writes one validated CSV per ticker
(the LATEST raw pull for that ticker) into data/processed/.

Run directly: python -m etl.clean
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

from etl.utils import load_config, get_logger, resolve_path

log = get_logger("clean")

REQUIRED_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume", "ticker"]
OUTLIER_THRESHOLD = 0.20  # flag single-day moves bigger than this


def _latest_file_per_ticker(raw_dir: Path) -> dict[str, Path]:
    """If extract.py has been run multiple times, only clean the most recent
    pull per ticker (files are named TICKER_YYYYMMDDTHHMMSS.csv)."""
    pattern = re.compile(r"^([A-Z]+)_(\d{8}T\d{6})\.csv$")
    latest: dict[str, tuple[str, Path]] = {}
    for f in raw_dir.glob("*.csv"):
        m = pattern.match(f.name)
        if not m:
            continue
        ticker, stamp = m.group(1), m.group(2)
        if ticker not in latest or stamp > latest[ticker][0]:
            latest[ticker] = (stamp, f)
    return {ticker: path for ticker, (_, path) in latest.items()}


def validate_schema(df: pd.DataFrame, ticker: str) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{ticker}: missing required columns {missing}")


def clean_ticker(df: pd.DataFrame, ticker: str) -> tuple[pd.DataFrame, dict]:
    report = {"ticker": ticker, "rows_in": len(df)}

    validate_schema(df, ticker)

    df["Date"] = pd.to_datetime(df["Date"], utc=True).dt.tz_localize(None)
    for col in ["Open", "High", "Low", "Close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").astype("Int64")

    # Drop exact duplicate (Date, ticker) rows, keep first
    before = len(df)
    df = df.drop_duplicates(subset=["Date", "ticker"], keep="first")
    report["duplicates_dropped"] = before - len(df)

    # Drop rows missing any core price field -- can't safely impute OHLC
    before = len(df)
    df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
    report["null_rows_dropped"] = before - len(df)

    df = df.sort_values("Date").reset_index(drop=True)

    # Flag (do not drop) large single-day moves for manual review
    df["daily_pct_change"] = df["Close"].pct_change()
    outliers = df[df["daily_pct_change"].abs() > OUTLIER_THRESHOLD]
    report["outliers_flagged"] = len(outliers)
    if len(outliers):
        log.warning(f"{ticker}: {len(outliers)} single-day moves > {OUTLIER_THRESHOLD:.0%} "
                    f"on {list(outliers['Date'].dt.date.astype(str))}")

    # Sanity check: High should be >= Low, Open, Close; Low should be <= all
    bad_rows = df[(df["High"] < df["Low"]) | (df["High"] < df["Open"]) |
                  (df["High"] < df["Close"]) | (df["Low"] > df["Open"]) |
                  (df["Low"] > df["Close"])]
    report["ohlc_consistency_violations"] = len(bad_rows)
    if len(bad_rows):
        log.warning(f"{ticker}: {len(bad_rows)} rows fail High/Low consistency checks")

    report["rows_out"] = len(df)
    return df, report


def run(config_path: str = None) -> list[dict]:
    cfg = load_config(config_path)
    raw_dir = resolve_path(cfg["paths"]["raw_dir"])
    processed_dir = resolve_path(cfg["paths"]["processed_dir"])
    processed_dir.mkdir(parents=True, exist_ok=True)

    latest_files = _latest_file_per_ticker(raw_dir)
    if not latest_files:
        raise FileNotFoundError(
            f"No raw CSVs found in {raw_dir}. Run `python -m etl.extract` "
            f"(or `python -m etl.demo_data` offline) first."
        )

    reports = []
    for ticker, path in latest_files.items():
        df = pd.read_csv(path)
        clean_df, report = clean_ticker(df, ticker)
        out_path = processed_dir / f"{ticker}_clean.csv"
        clean_df.to_csv(out_path, index=False)
        log.info(f"{ticker}: {report['rows_in']} -> {report['rows_out']} rows "
                  f"({report['duplicates_dropped']} dup, {report['null_rows_dropped']} null dropped, "
                  f"{report['outliers_flagged']} outliers flagged) -> {out_path.name}")
        reports.append(report)

    report_df = pd.DataFrame(reports)
    report_path = processed_dir / "_validation_report.csv"
    report_df.to_csv(report_path, index=False)
    log.info(f"Validation report written to {report_path}")
    return reports


if __name__ == "__main__":
    run()
