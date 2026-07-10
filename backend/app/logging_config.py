from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .config import Settings
from .security import redact


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, dict):
            record.msg = redact(record.msg)
        else:
            record.msg = str(redact(record.msg))
        return True


def configure_logging(settings: Settings) -> None:
    settings.logging.path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    redactor = RedactingFilter()

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.addFilter(redactor)
    root.addHandler(console)

    file_handler = RotatingFileHandler(settings.logging.path, maxBytes=2_000_000, backupCount=3)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(redactor)
    root.addHandler(file_handler)
