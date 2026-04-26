import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=True)


def configure_structured_logging(run_id: str, log_file: str = "trading.log") -> logging.Logger:
    logger = logging.getLogger("polybot")
    logger.setLevel(logging.INFO)
    logger.handlers = []
    logger.propagate = False

    formatter = JsonFormatter()

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)

    logger.info("logger_initialized", extra={"extra_fields": {"run_id": run_id}})
    return logger
