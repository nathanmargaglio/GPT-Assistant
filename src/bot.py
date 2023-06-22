import os
import sys
import datetime
import logging

from config import LOG_LEVEL, GPT_MODEL, DISCORD_BOT_TOKEN, LOG_TO_FILE

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

allowed_channels = [
    1120397916411007119,  # private DM with Nater5000
    1120447015168520294,  # assistant channel in Nater5000's server
]
allowed_authors = ["nater5000"]


class BotClient(discord.Client):
    async def on_ready(self):
        logger.info(f"Logged on as {self.user}")
        self.chatgpt = ChatGPT(gpt_model=GPT_MODEL)
        logger.info("ChatGPT initialized.")

    async def on_message(self, message):
        if message.author == self.user:
            return

        logger.info(
            f"Message: Channel {message.channel.id}/Author: {message.author}: {message.content}"
        )
        if message.channel.id not in allowed_channels:
            logger.info(f"Channel {message.channel.id} not allowed.")
            return

        if message.author.name not in allowed_authors:
            logger.info(f"Author {message.author} not allowed.")
            return

        if message.content.startswith("!"):
            command = message.content[1:]
            logger.info(f"Running command: {command}")
            command_output = os.popen(command).read()
            if command_output:
                await message.channel.send(command_output)
            else:
                await message.channel.send("No output available.")
            return

        # add a thinking emoji to indicate that the bot is working
        await message.add_reaction("🤔")
        logger.info("Sending message to GPT...")
        response_message = self.chatgpt.send_message(message.content)
        logger.info(f"Received response from GPT: {response_message}")
        # remove the thinking emoji
        await message.clear_reaction("🤔")
        await message.channel.send(response_message)


if __name__ == "__main__":
    intents = discord.Intents.default()
    intents.message_content = True
    client = BotClient(intents=intents)
    logger.info("Starting bot...")
    client.run(DISCORD_BOT_TOKEN)
