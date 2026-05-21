"""Logging configuration with rotating file handler."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(name: str = "trading_bot") -> logging.Logger:
    """
    Configure and return a logger that writes to both:
      • File:    logs/trading_bot.log  (DEBUG and above, rotating 5 MB × 3 backups)
      • Console: WARNING and above (keeps the terminal clean during normal use)
    """
    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / "trading_bot.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers when the module is re-imported
    # (e.g. Streamlit reruns, test suites)
    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── Rotating file handler ────────────────────────────────────────────────
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,   # 5 MB per file
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)

    # ── Console handler ──────────────────────────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Module-level singleton — imported as `from bot.logging_config import logger`
logger = setup_logger()
