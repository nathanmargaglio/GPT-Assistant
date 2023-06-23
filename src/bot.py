import os
import sys
import json
import logging

from config import LOG_LEVEL, LOG_TO_FILE, DISCORD_BOT_TOKEN, DISCORD_USERS

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
from db import DB


class BotClient(discord.Client):
    async def on_ready(self):
        logger.info(f"Logged on as {self.user}")
        self.db = DB()
        self.chatgpts = {}
        logger.info("Database initialized.")

    async def on_message(self, message):
        if message.author == self.user:
            return

        logger.info(f"> {message.author} ({message.channel.id}): {message.content}")

        if message.author.name in DISCORD_USERS:
            # admin commands
            if message.content.startswith(">>"):
                await self.run_system_command(message)
                return

            if message.content.startswith(">"):
                await self.run_command(message)
                return

        bot_configs = self.db.bot_configs
        for bot_name in bot_configs:
            config = bot_configs[bot_name]
            if message.channel.id in config["channel_ids"]:
                if bot_name not in self.chatgpts:
                    self.chatgpts[bot_name] = ChatGPT(db=self.db, name=bot_name)
                if config.get("include_username", False):
                    message.content = f"[{message.author.name}]: {message.content}"
                    logger.debug(f"Added username to message: {message.content}")
                if config.get("reply_to_mentions_only", False):
                    if self.user.mentioned_in(message):
                        # remove the mention from the message
                        message.content = message.content.replace(f"<@{self.user.id}>", "")
                        logger.debug(f"Removed mention from message: {message.content}")
                    else:
                        return
                chatgpt = self.chatgpts[bot_name]
                await self.chat(message, chatgpt)

    async def chat(self, message, chatgpt):
        await message.channel.typing()
        logger.debug("Sending message to GPT...")
        response_message = chatgpt.send_message(message.content)
        logger.info(f"> GPT: {response_message}")
        await message.channel.send(response_message)

    async def run_command(self, message):
        command = message.content[1:]
        logger.info(f"Running command: {command}")
        try:
            args = command.split(" ")
            if len(args) == 0:
                return

            if args[0] == "get":
                if len(args) == 2:
                    if args[1] == "config":
                        response = json.dumps(self.db.bot_configs, indent=4)
                        response = f"```json\n{response}\n```"
                        await message.channel.send(response)
                if len(args) == 3:
                    if args[1] == "config":
                        bot_name = args[2]
                        self.db.get_bot_configs()
                        response = json.dumps(self.db.bot_configs[bot_name], indent=4)
                        response = f"```json\n{response}\n```"
                        await message.channel.send(response)

            if args[0] == "set":
                if len(args) >= 3:
                    if args[1] == "config":
                        bot_name = args[2]
                        config_text = " ".join(args[3:])
                        config = json.loads(config_text)
                        self.db.set_config(bot_name, config)
                        self.db.get_bot_configs()
                        response = json.dumps(self.db.bot_configs[bot_name], indent=4)
                        response = f"```json\n{response}\n```"
                        await message.channel.send(response)

            if args[0] == "insert":
                if len(args) >= 3:
                    if args[1] == "config":
                        bot_name = args[2]
                        self.db.insert_config(bot_name)
                        self.db.get_bot_configs()
                        response = json.dumps(self.db.bot_configs[bot_name], indent=4)
                        response = f"```json\n{response}\n```"
                        await message.channel.send(response)
        except Exception as e:
            logger.error(e)
            await message.channel.send("Error: " + str(e))
        return

    async def run_system_command(self, message):
        command = message.content[1:]
        logger.info(f"Running system command: {command}")
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
