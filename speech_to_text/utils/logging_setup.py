"""
Logging setup for the speech-to-text application.
"""

import logging
import os
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
    
    # Configure logging
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file)
        ]
    )
    
    # Get the root logger
    logger = logging.getLogger()
    
    # Log startup information
    logger.info("Logging initialized")
    logger.info(f"Log file: {log_file}")
    
    return logger