import sys
import logging
from datetime import datetime
from typing import Optional
from rich.console import Console
from rich.logging import RichHandler

console = Console()

def setup_logger(name: str = "trucklead", log_level: str = "INFO") -> logging.Logger:
    """Configures structured console and file logging."""
    logger = logging.getLogger(name)
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # Avoid duplicate handlers
    if not logger.handlers:
        # Rich Handler for colorful, readable console logs
        rich_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            rich_tracebacks=True,
            markup=True
        )
        rich_handler.setLevel(numeric_level)
        formatter = logging.Formatter("[%(name)s] %(message)s")
        rich_handler.setFormatter(formatter)
        logger.addHandler(rich_handler)

    return logger

logger = setup_logger()
