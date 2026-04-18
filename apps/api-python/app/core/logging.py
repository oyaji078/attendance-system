from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

RESERVED_LOG_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__.keys())


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        extras = {key: value for key, value in record.__dict__.items() if key not in RESERVED_LOG_RECORD_FIELDS and not key.startswith("_")}
        if extras:
            payload.update(extras)
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level.upper())
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)

