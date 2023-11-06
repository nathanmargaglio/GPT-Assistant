import os
import sys
import logging
import logging.handlers
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def get_logger(logger_name):
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    logger = logging.getLogger(logger_name)
    
    logger.propagate = False

    if not logger.handlers:
        logger.setLevel(LOG_LEVEL)
        formatter = logging.Formatter("%(asctime)s - %(message)s")
        
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        
        file_handler = logging.handlers.RotatingFileHandler("bot.log", maxBytes=10 * 1024 * 1024, backupCount=5)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger
