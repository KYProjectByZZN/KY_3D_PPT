"""Application logging with bounded local files and a safe fallback."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .app_paths import logs_root


LOGGER_NAME = "ky_ppt_generator"


def configure_application_logging() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    try:
        directory = logs_root()
        directory.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = RotatingFileHandler(
            directory / "app.log",
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
    except OSError:
        handler = logging.NullHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


__all__ = ["LOGGER_NAME", "configure_application_logging"]
