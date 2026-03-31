import logging
import sys
from typing import Optional


LOG_FORMAT = (
    "%(asctime)s | %(levelname)s | %(name)s | "
    "trace_id=%(trace_id)s | %(message)s"
)


class TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "trace_id"):
            record.trace_id = "-"
        return True


def get_logger(name: str = "insurance_medical_kgqa", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.addFilter(TraceIdFilter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def log_with_trace(
    logger: logging.Logger,
    level: int,
    message: str,
    trace_id: Optional[str] = None,
) -> None:
    logger.log(level, message, extra={"trace_id": trace_id or "-"})
