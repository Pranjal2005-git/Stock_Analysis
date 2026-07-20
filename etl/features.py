"""
Phase 4 - Feature Engineering

Reads each cleaned ticker CSV from data/processed/ and adds technical
indicators: returns, SMA/EMA, RSI, MACD, Bollinger Bands, rolling
volatility, and a cross-ticker percentile rank on daily return.

Run directly: python -m etl.features
"""
from __future__ import annotations

import pandas as pd
import numpy as np

from etl.utils import load_config, get_logger, resolve_path

log = get_logger("features")


def add_returns(df: pd.DataFrame) -> pd.DataFrame:
    df["daily_return"] = df["Close"].pct_change()
    df["log_return"] = np.log(df["Close"] / df["Close"].shift(1))
    return df


def add_moving_averages(df: pd.DataFrame, sma_windows: list[int], ema_windows: list[int]) -> pd.DataFrame:
    for w in sma_windows:
        df[f"sma_{w}"] = df["Close"].rolling(window=w, min_periods=w).mean()
    for w in ema_windows:
        df[f"ema_{w}"] = df["Close"].ewm(span=w, adjust=False).mean()
    return df


def add_rsi(df: pd.DataFrame, window: int) -> pd.DataFrame:
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=window, min_periods=window).mean()
    avg_loss = loss.rolling(window=window, min_periods=window).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    # avg_loss == 0 with avg_gain > 0 means no down days in the window -> RSI = 100,
    # not NaN (which the divide-by-zero-guard above would otherwise produce).
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
    # avg_loss == 0 and avg_gain == 0 (flat price) is a genuine no-movement case -> RSI = 50.
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain == 0)), 50.0)
    df[f"rsi_{window}"] = rsi
    return df


def add_macd(df: pd.DataFrame, fast: int, slow: int, signal: int) -> pd.DataFrame:
    ema_fast = df["Close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=slow, adjust=False).mean()
    df["macd"] = ema_fast - ema_slow
    df["macd_signal"] = df["macd"].ewm(span=signal, adjust=False).mean()
    df["macd_histogram"] = df["macd"] - df["macd_signal"]
    return df


def add_bollinger_bands(df: pd.DataFrame, window: int, num_std: float) -> pd.DataFrame:
    mid = df["Close"].rolling(window=window, min_periods=window).mean()
    std = df["Close"].rolling(window=window, min_periods=window).std()
    df["bb_mid"] = mid
    df["bb_upper"] = mid + num_std * std
    df["bb_lower"] = mid - num_std * std
    return df


def add_volatility(df: pd.DataFrame, window: int) -> pd.DataFrame:
    df[f"volatility_{window}d"] = df["daily_return"].rolling(window=window, min_periods=window).std()
    return df


def build_features_for_ticker(df: pd.DataFrame, ind_cfg: dict) -> pd.DataFrame:
    df = df.sort_values("Date").reset_index(drop=True)
    df = add_returns(df)
    df = add_moving_averages(df, ind_cfg["sma_windows"], ind_cfg["ema_windows"])
    df = add_rsi(df, ind_cfg["rsi_window"])
    df = add_macd(df, ind_cfg["macd_fast"], ind_cfg["macd_slow"], ind_cfg["macd_signal"])
    df = add_bollinger_bands(df, ind_cfg["bollinger_window"], ind_cfg["bollinger_std"])
    df = add_volatility(df, ind_cfg["volatility_window"])
    return df


def run(config_path: str = None) -> pd.DataFrame:
    cfg = load_config(config_path)
    processed_dir = resolve_path(cfg["paths"]["processed_dir"])
    ind_cfg = cfg["indicators"]

    clean_files = sorted(processed_dir.glob("*_clean.csv"))
    if not clean_files:
        raise FileNotFoundError(
            f"No cleaned CSVs found in {processed_dir}. Run `python -m etl.clean` first."
        )

    all_frames = []
    for path in clean_files:
        ticker = path.stem.replace("_clean", "")
        df = pd.read_csv(path, parse_dates=["Date"])
        enriched = build_features_for_ticker(df, ind_cfg)
        out_path = processed_dir / f"{ticker}_features.csv"
        enriched.to_csv(out_path, index=False)
        log.info(f"{ticker}: computed {enriched.shape[1] - df.shape[1]} indicator columns -> {out_path.name}")
        all_frames.append(enriched)

    # Cross-ticker daily return percentile rank, useful for comparative analysis
    combined = pd.concat(all_frames, ignore_index=True)
    combined["return_rank_pct"] = combined.groupby("Date")["daily_return"].rank(pct=True)
    combined_path = processed_dir / "all_tickers_features.csv"
    combined.to_csv(combined_path, index=False)
    log.info(f"Combined feature set ({len(combined)} rows, {combined['ticker'].nunique()} tickers) -> {combined_path.name}")

    return combined


if __name__ == "__main__":
    run()
