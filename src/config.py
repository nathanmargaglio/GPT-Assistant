import os
import sys
import logging
import logging.handlers
from dotenv import load_dotenv

load_dotenv()

def get_env_variable(var_name, default=None, required=True):
    value = os.getenv(var_name, default)
    if required and not value:
        raise ValueError(f"{var_name} environment variable is missing from .env")
    return value

DISCORD_BOT_TOKEN = get_env_variable("DISCORD_BOT_TOKEN")
DISCORD_USERS = get_env_variable("DISCORD_USERS").split(",")
OPENAI_API_KEY = get_env_variable("OPENAI_API_KEY")
DB_URI = get_env_variable("DB_URI")
LOG_LEVEL = get_env_variable("LOG_LEVEL", default="INFO", required=False)
INSTANCE_ID = get_env_variable("INSTANCE_ID", default="default", required=False)
DISABLED = get_env_variable("DISABLED", default="false", required=False).lower() == "true"

def get_logger(logger_name):
    logger = logging.getLogger(logger_name)
    logger.setLevel(LOG_LEVEL.upper())
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    handler = logging.handlers.RotatingFileHandler("bot.log", maxBytes=10 * 1024 * 1024, backupCount=5)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
