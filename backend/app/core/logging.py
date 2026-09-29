import logging
import json
import sys
from datetime import datetime, timezone
from backend.app.core.config import settings


class JsonFormatter(logging.Formatter):
    """Emit one JSON diagnostic record per log event, including structured context."""

    STANDARD = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update({key: value for key, value in record.__dict__.items() if key not in self.STANDARD and not key.startswith("_")})
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging() -> logging.Logger:
    """Configures structured, informative logging for IncidentMind."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    for handler in logging.getLogger().handlers:
        handler.setFormatter(JsonFormatter())

    logger = logging.getLogger("incidentmind")
    logger.setLevel(log_level)
    return logger


logger = setup_logging()
