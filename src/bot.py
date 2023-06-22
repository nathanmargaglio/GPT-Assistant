import os
import sys
import datetime
import logging

from config import (
    LOG_LEVEL, LOG_TO_FILE,
    GPT_MODEL, DISCORD_BOT_TOKEN,
    DISCORD_CHANNELS, DISCORD_USERS
)

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL.upper())
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)
logger.addHandler(handler)

if LOG_TO_FILE:
    logger.debug("Logging to file...")
    handler = logging.FileHandler("bot.log")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

import discord
from gpt import ChatGPT

class BotClient(discord.Client):
    async def on_ready(self):
        logger.info(f"Logged on as {self.user}")
        self.chatgpt = ChatGPT(gpt_model=GPT_MODEL)
        logger.info("ChatGPT initialized.")

    async def on_message(self, message):
        if message.author == self.user:
            return

        logger.info(
            f"> {message.author}: {message.content}"
        )
        if message.channel.id not in DISCORD_CHANNELS:
            logger.info(f"Channel {message.channel.id} not allowed.")
            return

        if message.author.name not in DISCORD_USERS:
            logger.info(f"User {message.author} not allowed.")
            return

        if message.content.startswith(">"):
            self.run_command(message)
            return

        # add a thinking emoji to indicate that the bot is working
        message.add_reaction("🤔")
        logger.debug("Sending message to GPT...")
        response_message = self.chatgpt.send_message(message.content)
        logger.info(f"> Assistant: {response_message}")
        # remove the thinking emoji
        message.clear_reaction("🤔")
        await message.channel.send(response_message)
    
    async def run_command(self, message):
        command = message.content[1:]
        logger.info(f"Running command: {command}")
        command_output = os.popen(command).read()
        if command_output:
            await message.channel.send(command_output)
        else:
            await message.channel.send("No output available.")
        return

if __name__ == "__main__":
    intents = discord.Intents.default()
    intents.message_content = True
    client = BotClient(intents=intents)
    logger.info("Starting bot...")
    client.run(DISCORD_BOT_TOKEN)
