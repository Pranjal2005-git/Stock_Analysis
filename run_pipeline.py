"""
Orchestrates the full pipeline: extract -> clean -> features -> load.

Usage:
    python run_pipeline.py            # uses live yfinance (needs internet)
    python run_pipeline.py --demo     # uses synthetic offline data instead
"""
from __future__ import annotations

import argparse
import sys
import time

from etl import clean, features, load
from etl.utils import get_logger

log = get_logger("pipeline")


def main():
    parser = argparse.ArgumentParser(description="Run the stock analytics ETL pipeline")
    parser.add_argument("--demo", action="store_true",
                         help="Use synthetic offline data instead of live yfinance")
    parser.add_argument("--config", default=None, help="Path to config.yaml")
    args = parser.parse_args()

    start = time.time()
    log.info("=" * 60)
    log.info(f"Pipeline run starting (mode: {'DEMO/synthetic' if args.demo else 'LIVE yfinance'})")
    log.info("=" * 60)

    try:
        log.info("[1/4] Extract...")
        if args.demo:
            from etl import demo_data
            demo_data.run(args.config)
        else:
            from etl import extract
            extract.run(args.config)

        log.info("[2/4] Clean & validate...")
        clean.run(args.config)

        log.info("[3/4] Feature engineering...")
        features.run(args.config)

        log.info("[4/4] Load to database...")
        load.run(args.config)

    except Exception as e:
        log.error(f"Pipeline FAILED: {e}")
        sys.exit(1)

    elapsed = time.time() - start
    log.info(f"Pipeline completed successfully in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
