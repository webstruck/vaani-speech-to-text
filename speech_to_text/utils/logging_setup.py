"""
Logging setup for the speech-to-text application.
"""

import logging
import os
import sys
from datetime import datetime

def setup_logging(level=logging.INFO):
    """
    Set up logging for the application.

    Args:
        level: Logging level (default: INFO)

    Returns:
        Logger instance
    """
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(os.path.expanduser("~"), ".speech_to_text_app", "logs")
    os.makedirs(logs_dir, exist_ok=True)

    # Generate log filename with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(logs_dir, f"speech_to_text_{timestamp}.log")

    # Define the log format
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # --- Configure logging with explicit UTF-8 encoding ---
    # Remove basicConfig handlers if they exist, to avoid duplication
    # Get the root logger
    root_logger = logging.getLogger()
    # Remove existing handlers if any were added by basicConfig previously or by mistake
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Set the overall level for the root logger
    root_logger.setLevel(level)

    # Create formatter
    formatter = logging.Formatter(log_format)

    # Create File Handler with UTF-8 encoding
    try:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        # Fallback or just log to stderr if file handler fails
        print(f"Error setting up file logging: {e}", file=sys.stderr)


    # Create Stream Handler (Console)
    # For StreamHandler, the encoding is typically determined by the
    # terminal/console environment (e.g., sys.stderr.encoding).
    # Explicitly setting encoding here might not always work as expected,
    # but we can try setting an error handler like 'replace' or 'backslashreplace'
    # if console display issues persist, though the primary goal is to prevent crashes.
    stream_handler = logging.StreamHandler(sys.stdout) # Use stdout or stderr
    stream_handler.setFormatter(formatter)
    # Optional: Add error handling for console if needed, but often best left to terminal config
    # stream_handler.stream.reconfigure(errors='replace') # Example: replace unsupported chars with '?'
    root_logger.addHandler(stream_handler)

    # Get the logger for the current module (or root)
    logger = logging.getLogger() # Get the configured root logger

    # Log startup information
    logger.info("Logging initialized (using UTF-8 for file)")
    logger.info(f"Log file: {log_file}")

    return logger