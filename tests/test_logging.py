import logging

from app.core.logging import setup_logging


def test_logging_setup(caplog) -> None:
    setup_logging()

    logger = logging.getLogger("test")

    with caplog.at_level(logging.INFO):
        logger.info("test message")

    assert "test message" in caplog.text