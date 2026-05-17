import logging
from crawler.config.settings import LOG_LEVEL, LOG_FILE


def get_logger(name: str) -> logging.Logger:
    """Return a named child logger under the root 'crawler' logger."""
    return logging.getLogger(f"crawler.{name}")


def _setup_root_logger() -> None:
    root_logger = logging.getLogger("crawler")

    # Guard — prevent duplicate handlers if module is imported multiple times
    if root_logger.handlers:
        return

    root_logger.setLevel(getattr(logging, LOG_LEVEL))

    # ── Console Handler ───────────────────────────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S"
    ))

    # ── File Handler ──────────────────────────────────────────────────────────
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s:%(lineno)d  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


# Runs automatically when this module is imported
_setup_root_logger()