
import logging
import sys

def setup_logging(log_file='application.log', level=logging.INFO):
    """Configures logging for the application"""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

def get_logger(name):
    """Returns a logger instance with the given name"""
    return logging.getLogger(name)
