# Data Dictionary

## dim_ticker
| Column | Type | Description |
|---|---|---|
| ticker_id | SERIAL PK | Surrogate key |
| ticker | VARCHAR(10) | Ticker symbol (e.g. AAPL) |
| company_name | VARCHAR(100) | Display name |
| sector | VARCHAR(50) | GICS-style sector label |

## dim_date
| Column | Type | Description |
|---|---|---|
| date_id | SERIAL PK | Surrogate key |
| full_date | DATE | Calendar date |
| day_of_week | VARCHAR(10) | e.g. "Monday" |
| month | SMALLINT | 1-12 |
| quarter | SMALLINT | 1-4 |
| year | SMALLINT | Calendar year |
| is_trading_day | BOOLEAN | Currently always TRUE (only trading days are loaded) |

## fact_prices
One row per (ticker, date). OHLCV as pulled/generated in Phase 2, after
Phase 3 cleaning.
| Column | Type | Description |
|---|---|---|
| price_id | BIGSERIAL PK | Surrogate key |
| date_id | INT FK → dim_date | |
| ticker_id | INT FK → dim_ticker | |
| open, high, low, close | NUMERIC(12,4) | Daily OHLC |
| volume | BIGINT | Daily volume |

Unique constraint on (date_id, ticker_id) — this is what makes `load.py`'s
upsert idempotent.

## fact_indicators
One row per (ticker, date), computed in Phase 4.
| Column | Type | Description |
|---|---|---|
| indicator_id | BIGSERIAL PK | Surrogate key |
| date_id / ticker_id | INT FK | |
| daily_return | NUMERIC(12,6) | (close - prev_close) / prev_close |
| sma_20 / sma_50 / sma_200 | NUMERIC(12,4) | Simple moving averages |
| ema_12 / ema_26 | NUMERIC(12,4) | Exponential moving averages |
| rsi_14 | NUMERIC(6,2) | 14-day Relative Strength Index (0-100) |
| macd / macd_signal | NUMERIC(12,6) | MACD line and its 9-day EMA signal line |
| bb_upper / bb_lower | NUMERIC(12,4) | 20-day Bollinger Bands, 2 std dev |
| volatility_20d | NUMERIC(12,6) | 20-day rolling std. dev. of daily_return |

## mv_daily_summary (materialized view)
Pre-joined, pre-aggregated table refreshed after each load, used to keep
the Power BI KPI page fast. See `sql/analytics_queries.sql` query 8.
