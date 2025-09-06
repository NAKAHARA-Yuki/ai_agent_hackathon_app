"""
Shared logging configuration for Cloud Logging compatibility.

This module provides a single-line logging formatter that ensures all log output
appears on a single line, making it easier to read and correlate in Cloud Logging
environments where multi-line logs can be split into separate entries.
"""
import logging
import re


class SingleLineFormatter(logging.Formatter):
    """
    Custom formatter that ensures all log output is on a single line.
    
    This formatter converts multi-line log messages (including stack traces)
    into single-line entries by escaping newlines and other whitespace characters.
    This is particularly important for Cloud Logging environments where multi-line
    logs can be difficult to read and correlate.
    """
    
    def format(self, record):
        # Get the original formatted message
        msg = super().format(record)
        
        # Replace newlines and carriage returns with escaped versions
        # This preserves the content while making it single-line
        msg = msg.replace('\n', '\\n').replace('\r', '\\r')
        
        # Also replace tab characters for consistency
        msg = msg.replace('\t', '\\t')
        
        # Collapse multiple consecutive spaces to single space for cleaner output
        msg = re.sub(r'\s+', ' ', msg)
        
        return msg


def setup_cloud_logging(level_name="INFO", logger_name=None):
    """
    Set up logging with single-line output format optimized for Cloud Logging.
    
    Args:
        level_name (str): Log level name (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        logger_name (str): Name of logger to configure (None for root logger)
    
    Returns:
        logging.Logger: Configured logger instance
    """
    # Convert level name to logging constant
    try:
        level = getattr(logging, level_name.upper(), logging.INFO)
    except (AttributeError, TypeError):
        level = logging.INFO
    
    # Create formatter with single-line output
    formatter = SingleLineFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s - %(message)s"
    )
    
    # Get or create logger
    logger = logging.getLogger(logger_name)
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create and configure stream handler
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.setLevel(level)
    
    # Configure logger
    logger.addHandler(handler)
    logger.setLevel(level)
    
    # For named loggers, prevent propagation to avoid duplicate logs
    if logger_name:
        logger.propagate = False
    
    return logger


def configure_basic_cloud_logging(level_name="INFO", force=True):
    """
    Configure the root logger with cloud-friendly single-line formatting.
    
    This is a drop-in replacement for logging.basicConfig() that ensures
    single-line output suitable for Cloud Logging.
    
    Args:
        level_name (str): Log level name (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        force (bool): Whether to remove existing handlers first
    """
    # Convert level name to logging constant
    try:
        level = getattr(logging, level_name.upper(), logging.INFO)
    except (AttributeError, TypeError):
        level = logging.INFO
    
    # Get root logger
    root_logger = logging.getLogger()
    
    if force:
        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
    
    # Only add handler if none exist or force=True
    if not root_logger.handlers or force:
        # Create formatter
        formatter = SingleLineFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s - %(message)s"
        )
        
        # Create and configure handler
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        handler.setLevel(level)
        
        # Add to root logger
        root_logger.addHandler(handler)
    
    # Set level
    root_logger.setLevel(level)