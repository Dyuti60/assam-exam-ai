import logging
import sys


LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_HANDLER_MARKER = "_assam_exam_ai_handler"


def setup_logging() -> None:
    """Configure application-wide logging without replacing existing handlers."""

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Avoid adding our console handler multiple times.
    if any(
        getattr(handler, _HANDLER_MARKER, False)
        for handler in root_logger.handlers
    ):
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)

    formatter = logging.Formatter(LOG_FORMAT)
    handler.setFormatter(formatter)

    setattr(handler, _HANDLER_MARKER, True)

    root_logger.addHandler(handler)