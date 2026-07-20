import pandas as pd
import pytest

from etl.clean import clean_ticker


def make_raw_df():
    return pd.DataFrame({
        "Date": ["2024-01-01", "2024-01-02", "2024-01-02", "2024-01-03", "2024-01-04"],
        "Open": [100, 102, 102, None, 108],
        "High": [103, 104, 104, 107, 110],
        "Low": [99, 101, 101, 104, 106],
        "Close": [102, 103, 103, 106, 109],
        "Volume": [1_000_000, 1_100_000, 1_100_000, 900_000, 950_000],
        "ticker": ["TEST"] * 5,
    })


def test_removes_exact_duplicates():
    df = make_raw_df()
    clean_df, report = clean_ticker(df, "TEST")
    assert report["duplicates_dropped"] == 1
    assert clean_df["Date"].duplicated().sum() == 0


def test_drops_rows_missing_core_price_fields():
    df = make_raw_df()
    clean_df, report = clean_ticker(df, "TEST")
    assert report["null_rows_dropped"] == 1
    assert clean_df["Open"].isna().sum() == 0


def test_output_sorted_by_date():
    df = make_raw_df().iloc[::-1].reset_index(drop=True)  # shuffle order
    clean_df, _ = clean_ticker(df, "TEST")
    assert clean_df["Date"].is_monotonic_increasing


def test_missing_required_column_raises():
    df = make_raw_df().drop(columns=["Volume"])
    with pytest.raises(ValueError):
        clean_ticker(df, "TEST")


def test_flags_large_single_day_move_without_dropping_it():
    df = make_raw_df()
    df.loc[4, "Close"] = 300  # +190% jump from prior close
    clean_df, report = clean_ticker(df, "TEST")
    assert report["outliers_flagged"] >= 1
    # outlier is flagged, not removed
    assert 300 in clean_df["Close"].values
