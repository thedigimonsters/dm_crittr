from __future__ import annotations
import logging, logging.handlers
from pathlib import Path
from datetime import datetime
from app_config import APP_NAME, COMPANY_NAME, LOG_DIR

LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"{APP_NAME.lower()}.log"

def setup_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger()  # root
    logger.setLevel(level)

    # Clear duplicate handlers if reinit
    for h in list(logger.handlers):
        logger.removeHandler(h)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Rotating file
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=10_000_000, backupCount=5, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    fh.setLevel(level)
    logger.addHandler(fh)

    # Console (dev only)
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    ch.setLevel(level)
    logger.addHandler(ch)

    logger.info("%s logging initialised • %s • %s", APP_NAME, COMPANY_NAME, LOG_FILE)
    return logger

# Convenience helper so other modules consistently acquire loggers
def get_logger(name: str | None = None) -> logging.Logger:
    """
    Return a child logger of the root configured by setup_logging().
    Usage: from crittr.core.logging import get_logger; log = get_logger(__name__)
    """
    return logging.getLogger(name or APP_NAME)
