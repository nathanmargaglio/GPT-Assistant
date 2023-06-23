import os
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
LOG_TO_FILE = (
    get_env_variable("LOG_TO_FILE", default="False", required=False).lower() == "true"
)
LOG_LEVEL = get_env_variable("LOG_LEVEL", default="INFO", required=False)
