"""
Shared logging configuration for Cloud Logging compatibility.

This module provides a single-line logging formatter that ensures all log output
appears on a single line, making it easier to read and correlate in Cloud Logging
environments where multi-line logs can be split into separate entries.
"""
import logging
import re
from typing import Iterable


class SingleLineFormatter(logging.Formatter):
    """
    Custom formatter that ensures all log output is on a single line.
    
    This formatter converts multi-line log messages (including stack traces)
    into single-line entries by escaping newlines and other whitespace characters.
    This is particularly important for Cloud Logging environments where multi-line
    logs can be difficult to read and correlate.
    """
    
    def format(self, record):
        # 既存formatでexc_info等を文字列化
        msg = super().format(record)
        # 改行/復帰/タブを可視化
        msg = msg.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        # 連続空白圧縮 (意図的なインデントが Cloud Logging で崩れるのを許容)
        msg = re.sub(r' {2,}', ' ', msg)
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
    return root_logger


def _replace_handlers(loggers: Iterable[logging.Logger], formatter: logging.Formatter, level: int):
    for lg in loggers:
        try:
            for h in lg.handlers[:]:
                lg.removeHandler(h)
            h = logging.StreamHandler()
            h.setFormatter(formatter)
            h.setLevel(level)
            lg.addHandler(h)
            lg.setLevel(level)
            lg.propagate = False
        except Exception:
            continue


def enforce_single_line_all(level_name="INFO"):
    """既存の主要ロガー(gunicorn/access/flask/werkzeug等)を含め全て1行化フォーマットに統一。
    アプリ起動直後に呼び出す。"""
    try:
        level = getattr(logging, level_name.upper(), logging.INFO)
    except Exception:
        level = logging.INFO
    fmt = SingleLineFormatter(fmt="%(asctime)s %(levelname)s %(name)s - %(message)s")
    # ルート適用
    root = logging.getLogger()
    _replace_handlers([root], fmt, level)
    # 代表的サブロガー
    targets = []
    for name in [
        'gunicorn.error', 'gunicorn.access', 'werkzeug', 'server', 'agent', 'uvicorn', 'uvicorn.error', 'uvicorn.access'
    ]:
        targets.append(logging.getLogger(name))
    _replace_handlers(targets, fmt, level)
    return root