# gunicorn_config.py

bind = '0.0.0.0:8000'  # Bind to port 8000
workers = 4  # Number of worker processes
timeout = 300  # Worker timeout increased to 300 seconds

import logging
from logging.handlers import RotatingFileHandler

# Logging settings
loglevel = 'debug'
accesslog = 'gunicorn_access.log'
errorlog = 'gunicorn_error.log'

# Access log rotation
access_log_handler = RotatingFileHandler(accesslog, maxBytes=5*1024*1024, backupCount=2)
access_log_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
access_log_handler.setLevel(logging.DEBUG)

# Error log rotation
error_log_handler = RotatingFileHandler(errorlog, maxBytes=5*1024*1024, backupCount=2)
error_log_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
error_log_handler.setLevel(logging.DEBUG)

# Add handlers to Gunicorn loggers
gunicorn_logger = logging.getLogger('gunicorn.error')
gunicorn_logger.addHandler(error_log_handler)

gunicorn_access_logger = logging.getLogger('gunicorn.access')
gunicorn_access_logger.addHandler(access_log_handler)
