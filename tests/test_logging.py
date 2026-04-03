import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import main to trigger logging configuration
import main  # noqa: F401


def test_logging_configured():
    """Application should have logging configured."""
    logger = logging.getLogger("cses_api")
    assert logger.level != logging.NOTSET


def test_logging_effective_level():
    """Logging should have an effective handler via root logger."""
    logger = logging.getLogger("cses_api")
    assert logger.getEffectiveLevel() <= logging.INFO
