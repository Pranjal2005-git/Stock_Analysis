-- ============================================================
-- Phase 8 - SQL Analytics Layer: reusable views
-- Written against the star schema in schema.sql (PostgreSQL syntax).
-- ============================================================

-- Daily returns per ticker, computed in SQL via window functions
-- as a cross-check against the Python-computed daily_return.
CREATE OR REPLACE VIEW vw_daily_returns AS
SELECT
    t.ticker,
    d.full_date,
    p.close,
    LAG(p.close) OVER (PARTITION BY p.ticker_id ORDER BY d.full_date) AS prev_close,
    (p.close - LAG(p.close) OVER (PARTITION BY p.ticker_id ORDER BY d.full_date))
        / NULLIF(LAG(p.close) OVER (PARTITION BY p.ticker_id ORDER BY d.full_date), 0) AS daily_return
FROM fact_prices p
JOIN dim_ticker t ON t.ticker_id = p.ticker_id
JOIN dim_date d ON d.date_id = p.date_id;

-- Moving averages recomputed in pure SQL (20/50/200-day) for comparison
-- against the Python-side sma_20/50/200 stored in fact_indicators.
CREATE OR REPLACE VIEW vw_moving_averages AS
SELECT
    t.ticker,
    d.full_date,
    p.close,
    AVG(p.close) OVER (
        PARTITION BY p.ticker_id ORDER BY d.full_date
        ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ) AS sma_20_sql,
    AVG(p.close) OVER (
        PARTITION BY p.ticker_id ORDER BY d.full_date
        ROWS BETWEEN 49 PRECEDING AND CURRENT ROW
    ) AS sma_50_sql
FROM fact_prices p
JOIN dim_ticker t ON t.ticker_id = p.ticker_id
JOIN dim_date d ON d.date_id = p.date_id;

-- Rolling 52-week (approx. 252 trading day) high/low per ticker.
CREATE OR REPLACE VIEW vw_52_week_high_low AS
SELECT
    t.ticker,
    d.full_date,
    p.close,
    MAX(p.high) OVER (
        PARTITION BY p.ticker_id ORDER BY d.full_date
        ROWS BETWEEN 251 PRECEDING AND CURRENT ROW
    ) AS rolling_52w_high,
    MIN(p.low) OVER (
        PARTITION BY p.ticker_id ORDER BY d.full_date
        ROWS BETWEEN 251 PRECEDING AND CURRENT ROW
    ) AS rolling_52w_low
FROM fact_prices p
JOIN dim_ticker t ON t.ticker_id = p.ticker_id
JOIN dim_date d ON d.date_id = p.date_id;

-- Month-over-month and year-over-year close price, via CTEs.
CREATE OR REPLACE VIEW vw_mom_yoy_performance AS
WITH monthly_close AS (
    SELECT
        t.ticker,
        d.year,
        d.month,
        -- last trading day's close in each (ticker, year, month)
        FIRST_VALUE(p.close) OVER (
            PARTITION BY p.ticker_id, d.year, d.month
            ORDER BY d.full_date DESC
        ) AS month_end_close,
        d.full_date,
        ROW_NUMBER() OVER (
            PARTITION BY p.ticker_id, d.year, d.month
            ORDER BY d.full_date DESC
        ) AS rn
    FROM fact_prices p
    JOIN dim_ticker t ON t.ticker_id = p.ticker_id
    JOIN dim_date d ON d.date_id = p.date_id
)
SELECT
    ticker, year, month, month_end_close,
    LAG(month_end_close) OVER (PARTITION BY ticker ORDER BY year, month) AS prev_month_close,
    LAG(month_end_close, 12) OVER (PARTITION BY ticker ORDER BY year, month) AS prev_year_close
FROM monthly_close
WHERE rn = 1;