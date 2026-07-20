import pandas as pd
import numpy as np
import pytest

from etl.features import add_returns, add_moving_averages, add_rsi, add_macd, add_bollinger_bands


def make_price_df(closes):
    return pd.DataFrame({
        "Date": pd.date_range("2024-01-01", periods=len(closes), freq="B"),
        "Close": closes,
    })


def test_sma_matches_manual_calculation():
    closes = [10, 11, 12, 13, 14]
    df = make_price_df(closes)
    df = add_moving_averages(df, sma_windows=[3], ema_windows=[])
    # 3-day SMA for the last row should be mean(12, 13, 14) = 13
    assert df["sma_3"].iloc[-1] == 13.0
    # First two rows have < 3 data points -> NaN, not a guessed value
    assert df["sma_3"].iloc[0:2].isna().all()


def test_daily_return_calculation():
    df = make_price_df([100, 110, 99])
    df = add_returns(df)
    assert df["daily_return"].iloc[1] == pytest.approx(0.10)
    assert df["daily_return"].iloc[2] == pytest.approx(-0.10, abs=1e-6)


def test_rsi_is_100_when_no_losses():
    # Monotonically increasing prices -> avg_loss = 0 -> RSI should be 100
    closes = list(range(100, 120))
    df = make_price_df(closes)
    df = add_rsi(df, window=14)
    assert df["rsi_14"].iloc[-1] == 100.0


def test_macd_histogram_equals_macd_minus_signal():
    closes = [100 + i + (i % 5) for i in range(60)]
    df = make_price_df(closes)
    df = add_macd(df, fast=12, slow=26, signal=9)
    diff = (df["macd"] - df["macd_signal"] - df["macd_histogram"]).abs()
    assert (diff < 1e-9).all()


def test_bollinger_upper_above_lower():
    closes = [100 + (i % 7) for i in range(40)]
    df = make_price_df(closes)
    df = add_bollinger_bands(df, window=20, num_std=2)
    valid = df.dropna(subset=["bb_upper", "bb_lower"])
    assert (valid["bb_upper"] >= valid["bb_lower"]).all()
