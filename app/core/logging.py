import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler

from app.core.config import settings

ALARM_LOG_TO_FILE = os.getenv("ALARM_LOG_TO_FILE", "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
ALARM_LOG_FILE_PATH = os.getenv("ALARM_LOG_FILE_PATH", "logs/alarmas.txt")
ALARM_LOG_MAX_BYTES = int(os.getenv("ALARM_LOG_MAX_BYTES", "5242880"))
ALARM_LOG_BACKUP_COUNT = int(os.getenv("ALARM_LOG_BACKUP_COUNT", "5"))


def _ensure_parent_dir(file_path: str) -> None:
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        if ALARM_LOG_TO_FILE and name.startswith("alarms."):
            _ensure_parent_dir(ALARM_LOG_FILE_PATH)
            file_handler = RotatingFileHandler(
                ALARM_LOG_FILE_PATH,
                maxBytes=ALARM_LOG_MAX_BYTES,
                backupCount=ALARM_LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        logger.setLevel(
            getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
        )
        logger.propagate = False
    return logger
