-- ============================================================
-- Phase 8/9 - Documented analytics queries (PostgreSQL syntax)
-- ============================================================

-- 1. Latest close, RSI, and 20-day volatility for every ticker.
SELECT t.ticker, d.full_date, p.close, i.rsi_14, i.volatility_20d
FROM fact_prices p
JOIN fact_indicators i ON i.date_id = p.date_id AND i.ticker_id = p.ticker_id
JOIN dim_ticker t ON t.ticker_id = p.ticker_id
JOIN dim_date d ON d.date_id = p.date_id
WHERE d.full_date = (SELECT MAX(full_date) FROM dim_date)
ORDER BY t.ticker;

-- 2. Top 10 single-day gainers across all tickers.
SELECT t.ticker, d.full_date, i.daily_return
FROM fact_indicators i
JOIN dim_ticker t ON t.ticker_id = i.ticker_id
JOIN dim_date d ON d.date_id = i.date_id
ORDER BY i.daily_return DESC
LIMIT 10;

-- 3. Top 10 single-day losers across all tickers.
SELECT t.ticker, d.full_date, i.daily_return
FROM fact_indicators i
JOIN dim_ticker t ON t.ticker_id = i.ticker_id
JOIN dim_date d ON d.date_id = i.date_id
ORDER BY i.daily_return ASC
LIMIT 10;

-- 4. Volatility ranking: average 20-day volatility per ticker, most to least volatile.
SELECT t.ticker, ROUND(AVG(i.volatility_20d)::numeric, 5) AS avg_20d_volatility
FROM fact_indicators i
JOIN dim_ticker t ON t.ticker_id = i.ticker_id
GROUP BY t.ticker
ORDER BY avg_20d_volatility DESC;

-- 5. Cross-ticker correlation of daily returns (pairwise, via self-join).
-- Returns one row per ticker pair with the Pearson correlation of daily_return.
SELECT
    a.ticker AS ticker_a,
    b.ticker AS ticker_b,
    ROUND(CORR(ia.daily_return, ib.daily_return)::numeric, 4) AS correlation
FROM fact_indicators ia
JOIN fact_indicators ib
    ON ia.date_id = ib.date_id AND ia.ticker_id < ib.ticker_id
JOIN dim_ticker a ON a.ticker_id = ia.ticker_id
JOIN dim_ticker b ON b.ticker_id = ib.ticker_id
GROUP BY a.ticker, b.ticker
ORDER BY correlation DESC;

-- 6. Days each ticker's RSI was in overbought (>70) or oversold (<30) territory.
SELECT
    t.ticker,
    COUNT(*) FILTER (WHERE i.rsi_14 > 70) AS days_overbought,
    COUNT(*) FILTER (WHERE i.rsi_14 < 30) AS days_oversold,
    COUNT(*) AS total_days
FROM fact_indicators i
JOIN dim_ticker t ON t.ticker_id = i.ticker_id
GROUP BY t.ticker
ORDER BY days_overbought DESC;

-- 7. Cumulative return since the start of the loaded history, per ticker.
WITH first_close AS (
    SELECT p.ticker_id, p.close AS start_close
    FROM fact_prices p
    JOIN dim_date d ON d.date_id = p.date_id
    WHERE (p.ticker_id, d.full_date) IN (
        SELECT ticker_id, MIN(full_date)
        FROM fact_prices fp JOIN dim_date dd ON dd.date_id = fp.date_id
        GROUP BY ticker_id
    )
)
SELECT
    t.ticker,
    d.full_date,
    p.close,
    ROUND(((p.close - fc.start_close) / fc.start_close * 100)::numeric, 2) AS cumulative_return_pct
FROM fact_prices p
JOIN dim_ticker t ON t.ticker_id = p.ticker_id
JOIN dim_date d ON d.date_id = p.date_id
JOIN first_close fc ON fc.ticker_id = p.ticker_id
ORDER BY t.ticker, d.full_date;

-- 8. Materialized view refreshed after each pipeline load: a fast
-- pre-aggregated summary table for the Power BI dashboard's KPI page.
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_summary AS
SELECT
    t.ticker,
    d.full_date,
    p.close,
    i.daily_return,
    i.sma_50,
    i.rsi_14,
    i.volatility_20d,
    RANK() OVER (PARTITION BY d.full_date ORDER BY i.daily_return DESC) AS return_rank_today
FROM fact_prices p
JOIN fact_indicators i ON i.date_id = p.date_id AND i.ticker_id = p.ticker_id
JOIN dim_ticker t ON t.ticker_id = p.ticker_id
JOIN dim_date d ON d.date_id = p.date_id;

-- Refresh after each load.py run (call from the pipeline or a cron step):
-- REFRESH MATERIALIZED VIEW mv_daily_summary;

-- 9. Sector-level average daily return (demonstrates benchmark-style grouping;
-- meaningful once more tickers/sectors are added to dim_ticker).
SELECT t.sector, d.full_date, AVG(i.daily_return) AS avg_sector_return
FROM fact_indicators i
JOIN dim_ticker t ON t.ticker_id = i.ticker_id
JOIN dim_date d ON d.date_id = i.date_id
GROUP BY t.sector, d.full_date
ORDER BY d.full_date DESC, t.sector;
