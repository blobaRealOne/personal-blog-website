"""Application configuration and shared resources.

Defines application-wide settings, filesystem paths, data validation
limits, and shared synchronization primitives.

Also configures the application logger with a rotating file handler
to manage persistent log output.
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock

BASE_PATH = Path(__file__).resolve().parent
ARTICLE_PATH = BASE_PATH / "articles"

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")
SECRET_KEY = os.environ.get("SECRET_KEY", "secret_key")

ARTICLE_LOCK = Lock()

MAX_TITLE_LENGTH = 120
MAX_CONTENT_LENGTH = 50_000
MAX_USERNAME_LENGTH = 40
MAX_COMMENT_LENGTH = 3_000

logger = logging.getLogger("personal_blog")


def configure_file_logging() -> None:
    """Configures rotating file logging for the application.

    Creates a RotatingFileHandler that writes logs to logfile.log.
    The log file is limited to 1 MB, with up to three backup files retained.

    Avoids registering another handler if the same log file is already
    configured.

    The application logger is configured at INFO level and propagation
    to parent loggers is disabled.
    """
    log_path = (BASE_PATH / "logfile.log").resolve()

    for handler in logger.handlers:
        if (
            isinstance(handler, RotatingFileHandler)
            and Path(handler.baseFilename).resolve() == log_path
        ):
            return

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )

    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s - [%(levelname)s] %(name)s -> %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
