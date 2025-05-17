
import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logging():
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Configure logging
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # File handler for all logs
    file_handler = RotatingFileHandler(
        'logs/app.log', 
        maxBytes=10000000,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    
    # Error file handler
    error_handler = RotatingFileHandler(
        'logs/error.log',
        maxBytes=10000000,
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)
