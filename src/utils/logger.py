"""Application-wide logging configuration."""

from __future__ import annotations

import logging

from config.settings import APP

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def get_logger(name: str) -> logging.Logger:
    """Return a logger configured with the application format and level.

    Handlers are attached only once per logger, so Streamlit reruns do not
    produce duplicate log lines.

    Args:
        name: Logger name, usually ``__name__``.

    Returns:
        A configured ``logging.Logger``.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logger.addHandler(handler)
        logger.propagate = False
    logger.setLevel(APP.log_level.upper())
    return logger
