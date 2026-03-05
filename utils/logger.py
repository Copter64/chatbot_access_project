"""Logging configuration module.

Provides centralized logging setup with colored output and file logging.
"""

import logging
import os
from typing import Optional

import coloredlogs

from config import Config


def setup_logger(
    name: str = "gameserver_bot",
    level: Optional[str] = None,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """Set up and configure logger with colored console output.

    Args:
        name: Logger name.
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Optional file path for log output.

    Returns:
        logging.Logger: Configured logger instance.
    """
    # Use provided level or fall back to config
    log_level = level or Config.LOG_LEVEL
    log_file = log_file or Config.LOG_FILE

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Define log format
    log_format = (
        "%(asctime)s - %(name)s - %(levelname)s - "
        "%(filename)s:%(lineno)d - %(message)s"
    )

    # Set up colored console logging
    coloredlogs.install(
        level=log_level.upper(),
        logger=logger,
        fmt=log_format,
        level_styles={
            "debug": {"color": "cyan"},
            "info": {"color": "green"},
            "warning": {"color": "yellow", "bold": True},
            "error": {"color": "red", "bold": True},
            "critical": {"color": "red", "bold": True, "background": "yellow"},
        },
        field_styles={
            "asctime": {"color": "white"},
            "hostname": {"color": "magenta"},
            "levelname": {"color": "white", "bold": True},
            "name": {"color": "blue"},
            "programname": {"color": "cyan"},
        },
    )

    # Set up file logging if log_file is specified
    if log_file:
        # Ensure log directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir:
            try:
                os.makedirs(log_dir, exist_ok=True)
            except PermissionError:
                print(
                    f"Warning: Cannot create log directory {log_dir}. "
                    "Logging to console only."
                )
                return logger
            except Exception as e:
                print(
                    f"Warning: Error creating log directory {log_dir}: {e}. "
                    "Logging to console only."
                )
                return logger

        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(
                getattr(logging, log_level.upper(), logging.INFO)
            )
            file_formatter = logging.Formatter(log_format)
            file_handler.setFormatter(file_formatter)

            # Force flush after each log to ensure logs are written immediately
            class FlushingFileHandler(logging.FileHandler):
                def emit(self, record):
                    super().emit(record)
                    self.flush()

            file_handler = FlushingFileHandler(log_file)
            file_handler.setLevel(
                getattr(logging, log_level.upper(), logging.INFO)
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except PermissionError:
            print(
                f"Warning: Cannot create log file {log_file}. "
                "Logging to console only."
            )

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name.

    Returns:
        logging.Logger: Logger instance.
    """
    return logging.getLogger(name)


# Create default logger
logger = setup_logger()
