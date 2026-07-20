"""Shared helpers: config loading and logging setup.

Keeping this in one place means every script (extract/clean/features/load)
reads tickers, date ranges, and indicator parameters the same way instead of
each hardcoding its own copy.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_config(config_path: str | Path = None) -> dict[str, Any]:
    path = Path(config_path) if config_path else PROJECT_ROOT / "config.yaml"
    with open(path, "r") as f:
        return yaml.safe_load(f)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
        )
        logger.addHandler(handler)

        file_handler = logging.FileHandler(PROJECT_ROOT / "pipeline.log")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
        )
        logger.addHandler(file_handler)
    return logger


def resolve_path(relative: str) -> Path:
    """Resolve a path from config.yaml relative to the project root."""
    return PROJECT_ROOT / relative
