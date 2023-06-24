from config import DISCORD_BOT_TOKEN, get_logger

logger = get_logger(__name__)

import discord
from bot import BotClient

if __name__ == "__main__":
    intents = discord.Intents.default()
    intents.message_content = True
    client = BotClient(intents=intents)
    logger.info("Starting bot...")
    client.run(DISCORD_BOT_TOKEN)
