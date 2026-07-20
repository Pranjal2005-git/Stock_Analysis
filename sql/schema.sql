-- ============================================================
-- Stock Market Analytics -- PostgreSQL Schema (Phase 5)
-- Star schema: 2 dimension tables + 2 fact tables.
-- ============================================================

CREATE TABLE IF NOT EXISTS dim_ticker (
    ticker_id     SERIAL PRIMARY KEY,
    ticker        VARCHAR(10) NOT NULL UNIQUE,
    company_name  VARCHAR(100),
    sector        VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_id         SERIAL PRIMARY KEY,
    full_date       DATE NOT NULL UNIQUE,
    day_of_week     VARCHAR(10),
    month           SMALLINT,
    quarter         SMALLINT,
    year            SMALLINT,
    is_trading_day  BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS fact_prices (
    price_id    BIGSERIAL PRIMARY KEY,
    date_id     INTEGER NOT NULL REFERENCES dim_date(date_id),
    ticker_id   INTEGER NOT NULL REFERENCES dim_ticker(ticker_id),
    open        NUMERIC(12, 4),
    high        NUMERIC(12, 4),
    low         NUMERIC(12, 4),
    close       NUMERIC(12, 4),
    volume      BIGINT,
    CONSTRAINT uq_fact_prices_date_ticker UNIQUE (date_id, ticker_id)
);

CREATE TABLE IF NOT EXISTS fact_indicators (
    indicator_id    BIGSERIAL PRIMARY KEY,
    date_id         INTEGER NOT NULL REFERENCES dim_date(date_id),
    ticker_id       INTEGER NOT NULL REFERENCES dim_ticker(ticker_id),
    daily_return    NUMERIC(12, 6),
    sma_20          NUMERIC(12, 4),
    sma_50          NUMERIC(12, 4),
    sma_200         NUMERIC(12, 4),
    ema_12          NUMERIC(12, 4),
    ema_26          NUMERIC(12, 4),
    rsi_14          NUMERIC(6, 2),
    macd            NUMERIC(12, 6),
    macd_signal     NUMERIC(12, 6),
    bb_upper        NUMERIC(12, 4),
    bb_lower        NUMERIC(12, 4),
    volatility_20d  NUMERIC(12, 6),
    CONSTRAINT uq_fact_indicators_date_ticker UNIQUE (date_id, ticker_id)
);

-- Indexes to speed up the time-series + per-ticker lookups the dashboard
-- and analytics queries do constantly.
CREATE INDEX IF NOT EXISTS idx_fact_prices_ticker_date
    ON fact_prices (ticker_id, date_id);

CREATE INDEX IF NOT EXISTS idx_fact_indicators_ticker_date
    ON fact_indicators (ticker_id, date_id);

CREATE INDEX IF NOT EXISTS idx_dim_date_full_date
    ON dim_date (full_date);

-- ============================================================
-- ER relationships (for the architecture diagram / README):
--   dim_ticker (1) ----< fact_prices (many)
--   dim_date   (1) ----< fact_prices (many)
--   dim_ticker (1) ----< fact_indicators (many)
--   dim_date   (1) ----< fact_indicators (many)
-- ============================================================