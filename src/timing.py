from __future__ import annotations

import logging
import time
from collections.abc import Callable
from contextlib import contextmanager
from typing import TypeVar

logger = logging.getLogger("oem_manuals.timing")

T = TypeVar("T")

_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"
_LOG_DATEFMT = "%H:%M:%S"
_OEM_LOGGERS = (
    "oem_manuals",
    "oem_manuals.pipeline",
    "oem_manuals.search",
    "oem_manuals.timing",
)
_QUIET_LOGGERS = (
    "azure",
    "urllib3",
    "httpx",
    "httpcore",
    "openai",
)


def configure_logging(level: int = logging.INFO) -> None:
    """Enable concise pipeline/search timing logs; suppress SDK HTTP noise."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATEFMT))

    for name in _OEM_LOGGERS:
        log = logging.getLogger(name)
        log.setLevel(level)
        log.handlers.clear()
        log.addHandler(handler)
        log.propagate = False

    for name in _QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    logging.getLogger().setLevel(logging.WARNING)


@contextmanager
def log_step(step: str, *, extra: str | None = None):
    label = f"{step} ({extra})" if extra else step
    start = time.perf_counter()
    logger.info("Started: %s", label)
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        logger.info("Finished: %s in %.2fs", label, elapsed)


def log_sync_step(step: str, func: Callable[..., T], /, *args, **kwargs) -> T:
    with log_step(step):
        return func(*args, **kwargs)
