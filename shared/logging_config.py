"""
Shared logging configuration for Cloud Logging compatibility.

This module provides a single-line logging formatter that ensures all log output
appears on a single line, making it easier to read and correlate in Cloud Logging
environments where multi-line logs can be split into separate entries.
"""
import logging
import json
from datetime import datetime, timezone
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


def enforce_json_all(level_name: str = "INFO"):
    """Apply GoogleCloudJsonFormatter to major loggers (gunicorn, werkzeug, etc.)."""
    try:
        level = getattr(logging, level_name.upper(), logging.INFO)
    except Exception:
        level = logging.INFO
    fmt = GoogleCloudJsonFormatter()
    # Root
    root = logging.getLogger()
    _replace_handlers([root], fmt, level)
    # Common child loggers
    targets = []
    for name in [
        'gunicorn.error', 'gunicorn.access', 'werkzeug', 'server', 'agent', 'uvicorn', 'uvicorn.error', 'uvicorn.access'
    ]:
        targets.append(logging.getLogger(name))
    _replace_handlers(targets, fmt, level)
    return root


class GoogleCloudJsonFormatter(logging.Formatter):
    """Structured JSON formatter tailored for Google Cloud Logging.

    Emits JSON with fields recognized by Cloud Logging so entries are parsed
    and correlated with Cloud Trace when 'trace' and 'spanId' are present.
    """

    # Map Python levelnames to GCP severities (same strings are fine)
    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        try:
            message = record.getMessage()
        except Exception:
            message = getattr(record, 'message', str(record))

        # Base payload
        payload = {
            'severity': record.levelname,
            'message': message,
            'logger': record.name,
        }

        # Attach trace correlation if available
        trace = getattr(record, 'trace', None)
        if trace:
            payload['trace'] = trace
        span_id = getattr(record, 'spanId', None) or getattr(record, 'span_id', None)
        if span_id:
            payload['spanId'] = str(span_id)
        trace_sampled = getattr(record, 'trace_sampled', None)
        if trace_sampled is not None:
            payload['traceSampled'] = bool(trace_sampled)

        # HTTP request structured info, if provided by the logger
        http_req = getattr(record, 'httpRequest', None)
        if isinstance(http_req, dict):
            payload['httpRequest'] = http_req

        # Optional bodies for debug tracing
        req_body = getattr(record, 'requestBody', None)
        if req_body is not None:
            payload['requestBody'] = req_body
        resp_body = getattr(record, 'responseBody', None)
        if resp_body is not None:
            payload['responseBody'] = resp_body

        # Labels namespace for Cloud Logging
        labels = getattr(record, 'labels', None)
        if isinstance(labels, dict):
            payload['logging.googleapis.com/labels'] = labels

        # Source location (optional but helpful)
        payload['logging.googleapis.com/sourceLocation'] = {
            'file': record.pathname,
            'line': record.lineno,
            'function': record.funcName,
        }

        # Optional timestamp (platform assigns one; include for clarity in local runs)
        try:
            ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
            payload['time'] = ts
        except Exception:
            pass

        try:
            return json.dumps(payload, ensure_ascii=False)
        except Exception:
            # Fallback to single-line text if JSON encoding fails
            txt = f"{record.levelname} {record.name} - {message}"
            return txt.replace('\n', ' ').replace('\r', ' ')


def configure_gcp_json_logging(level_name: str = "INFO", force: bool = True, labels: dict | None = None):
    """Configure root logger to emit Google Cloud structured JSON to stdout.

    Args:
        level_name: log level
        force: remove existing handlers
        labels: optional constant labels to attach via formatter (applied via Filter)

    Returns:
        logging.Logger: configured root logger
    """
    try:
        level = getattr(logging, level_name.upper(), logging.INFO)
    except Exception:
        level = logging.INFO

    root = logging.getLogger()
    if force:
        for h in root.handlers[:]:
            root.removeHandler(h)

    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(GoogleCloudJsonFormatter())
    if labels:
        class _ConstLabelsFilter(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                # Don't overwrite if already set by request-scoped filter
                if not hasattr(record, 'labels') or not isinstance(getattr(record, 'labels'), dict):
                    setattr(record, 'labels', labels)
                else:
                    # Merge without clobbering existing keys
                    merged = dict(labels)
                    merged.update(getattr(record, 'labels'))
                    setattr(record, 'labels', merged)
                return True
        handler.addFilter(_ConstLabelsFilter())

    root.addHandler(handler)
    root.setLevel(level)
    return root