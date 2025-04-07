"""
Error handling utilities for the speech-to-text application.
"""

import logging
import traceback
import functools

logger = logging.getLogger(__name__)

def log_exceptions(func):
    """
    Decorator to log exceptions that occur in a function.
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            raise  # Re-raise the exception after logging
    return wrapper

def safe_execution(default_value=None, log_error=True):
    """
    Decorator for functions that should never raise exceptions.
    
    Args:
        default_value: Value to return if an exception occurs
        log_error: Whether to log exceptions
        
    Returns:
        Decorator function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_error:
                    logger.error(f"Error in {func.__name__}: {str(e)}")
                    logger.error(traceback.format_exc())
                return default_value
        return wrapper
    return decorator