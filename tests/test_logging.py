import logging

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import main to trigger logging configuration
import main  # noqa: F401


def test_logging_configured():
    """Application should have logging configured."""
    logger = logging.getLogger('cses_api')
    assert logger.level != logging.NOTSET


def test_logging_handler_attached():
    """Application should have logging handlers."""
    logger = logging.getLogger('cses_api')
    assert len(logger.handlers) > 0
