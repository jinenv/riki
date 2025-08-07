# src/utils/logger.py
import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler
import json

class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add extra fields if present
        if hasattr(record, 'player_id'):
            log_entry["player_id"] = record.player_id
        
        if hasattr(record, 'transaction_type'):
            log_entry["transaction_type"] = record.transaction_type
        
        if hasattr(record, 'transaction'):
            log_entry["transaction"] = record.transaction
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)

def setup_logging(log_level: str = "INFO", log_to_file: bool = True) -> None:
    """Setup application logging configuration"""
    
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler with simple format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)
    
    if log_to_file:
        # Main application log with JSON format
        app_handler = RotatingFileHandler(
            log_dir / "seio_app.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        app_handler.setLevel(logging.DEBUG)
        app_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(app_handler)
        
        # Transaction log (separate file for audit trail)
        transaction_handler = RotatingFileHandler(
            log_dir / "seio_transactions.log",
            maxBytes=50*1024*1024,  # 50MB
            backupCount=10
        )
        transaction_handler.setLevel(logging.INFO)
        transaction_handler.setFormatter(JSONFormatter())
        
        # Filter to only transaction logs
        transaction_handler.addFilter(
            lambda record: hasattr(record, 'transaction_type')
        )
        root_logger.addHandler(transaction_handler)
        
        # Error log (separate file for errors only)
        error_handler = RotatingFileHandler(
            log_dir / "seio_errors.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(error_handler)
    
    # Suppress noisy third-party loggers
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    logging.info("Logging system initialized")

def get_logger(name: str) -> logging.Logger:
    """Get logger instance for module"""
    return logging.getLogger(name)