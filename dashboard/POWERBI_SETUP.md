# Power BI Dashboard Setup (Phase 10)

Power BI Desktop is Windows-only and can't be run inside this build
environment, so this repo ships everything needed to build the real
`.pbix` yourself in a few minutes:

- `dashboard/powerbi_exports/fact_table_export.csv` — a flattened, ready-to-import
  export joining prices + indicators + ticker/sector (one row per ticker per day).
- `dashboard/dashboard_preview.png` — a static preview of what the four report
  pages below look like, generated from the same data with matplotlib.

## 1. Connect

Open Power BI Desktop → **Get Data** → **PostgreSQL database** → point it at
your `stock_analytics` database (see README for connection details) and
import `fact_prices`, `fact_indicators`, `dim_ticker`, `dim_date`, and the
`mv_daily_summary` materialized view. (No Postgres yet? Import
`fact_table_export.csv` directly via **Get Data → Text/CSV** to prototype
the report pages immediately.)

## 2. DAX measures

```
YoY Growth % =
DIVIDE(
    [Latest Close] - CALCULATE([Latest Close], SAMEPERIODLASTYEAR('dim_date'[full_date])),
    CALCULATE([Latest Close], SAMEPERIODLASTYEAR('dim_date'[full_date]))
)

Rolling 30D Return % =
VAR CurrentClose = [Latest Close]
VAR PastClose = CALCULATE([Latest Close], DATEADD('dim_date'[full_date], -30, DAY))
RETURN DIVIDE(CurrentClose - PastClose, PastClose)

Volatility Rank =
RANKX(ALL('dim_ticker'[ticker]), CALCULATE(AVERAGE('fact_indicators'[volatility_20d])), , DESC)

Latest Close =
CALCULATE(MAX('fact_prices'[close]), LASTDATE('dim_date'[full_date]))
```

## 3. Report pages

1. **Price Trends & Moving Averages** — line chart of Close/SMA20/SMA50/SMA200
   per ticker, with a ticker slicer.
2. **Technical Indicators** — RSI and MACD combo charts with overbought/oversold
   reference lines at 70/30.
3. **Comparative Performance & Correlation** — matrix/heatmap visual of the
   pairwise return correlation (query 5 in `sql/analytics_queries.sql`), plus
   a small-multiples return chart across all 5 tickers.
4. **Summary KPI page** — cards for latest close, YoY growth, and volatility
   rank per ticker, backed by `mv_daily_summary`.

Add a ticker slicer and a date-range slicer on every page, synced across pages
(**Format → Edit interactions**, sync slicers).
