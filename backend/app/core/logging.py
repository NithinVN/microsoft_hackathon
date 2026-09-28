import logging
import sys
from backend.app.core.config import settings


def setup_logging() -> logging.Logger:
    """Configures structured, informative logging for IncidentMind."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    log_format = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    logger = logging.getLogger("incidentmind")
    logger.setLevel(log_level)
    return logger


logger = setup_logging()
