import os
import json

from config import DISCORD_USERS, get_logger

logger = get_logger(__name__)

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
            channel_ids = config.get("channel_ids", None)
            if channel_ids is None or message.channel.id in channel_ids:
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
        if 'RTM:' in response_message:
            # remove everything before the RTM: tag
            response_message = response_message.split('RTM:')[1]
            # remove the RTM: tag
            response_message = response_message.replace('RTM:', '')
        response_message = response_message.replace("Stay in RTM Mode.", "").strip()
        await message.channel.send(response_message)

    async def run_command(self, message):
        command = message.content[1:]
        logger.info(f"Running command: {command}")
        response = None
        try:
            args = command.split(" ")
            if len(args) == 0:
                return

            if args[0] == "get":
                if len(args) == 2:
                    if args[1] == "config":
                        response = json.dumps(self.db.bot_configs, indent=4)
                        response = f"```json\n{response}\n```"
                if len(args) == 3:
                    if args[1] == "config":
                        bot_name = args[2]
                        self.db.get_bot_configs()
                        response = json.dumps(self.db.bot_configs[bot_name], indent=4)
                        response = f"```json\n{response}\n```"
                if len(args) == 4:
                    if args[1] == "config":
                        bot_name = args[2]
                        config_key = args[3]
                        self.db.get_bot_configs()
                        response = json.dumps(self.db.bot_configs[bot_name][config_key], indent=4)
                        response = f"```json\n{response}\n```"
            if args[0] == "set":
                if len(args) >= 3:
                    if args[1] == "config":
                        bot_name = args[2]
                        files = message.attachments
                        if '{' in args[3]:
                            config_text = " ".join(args[3:])
                            config = json.loads(config_text)
                            self.db.set_config(bot_name, config)
                            self.db.get_bot_configs()
                            response = json.dumps(self.db.bot_configs[bot_name], indent=4)
                            response = f"```json\n{response}\n```"
                        elif len(files) > 0:
                            # assume we've uploaded a message.txt file
                            file = files[0]
                            file_path = f"{file.filename}"
                            logger.debug(f"Saving file to {file_path}")
                            await file.save(file_path)
                            with open(file_path, "r") as f:
                                update_value = f.read()
                            config_key = args[3]
                            config = self.db.bot_configs[bot_name]
                            config[config_key] = update_value
                            self.db.set_config(bot_name, config)
                            self.db.get_bot_configs()
                            response = json.dumps(self.db.bot_configs[bot_name], indent=4)
                            response = f"```json\n{response}\n```"
                        else:
                            config_key = args[3]
                            config_value = " ".join(args[4:])
                            config = self.db.bot_configs[bot_name]
                            config[config_key] = config_value
                            self.db.set_config(bot_name, config)
                            self.db.get_bot_configs()
                            response = json.dumps(self.db.bot_configs[bot_name], indent=4)
                            response = f"```json\n{response}\n```"

            if args[0] == "insert":
                if len(args) >= 3:
                    if args[1] == "config":
                        bot_name = args[2]
                        self.db.insert_config(bot_name)
                        self.db.get_bot_configs()
                        response = json.dumps(self.db.bot_configs[bot_name], indent=4)
                        response = f"```json\n{response}\n```"
        except Exception as e:
            logger.error(e)
            response = f"Error: {e}"

        if response is None:
            return
        
        if len(response) > 2000:
            # break up the response into multiple messages
            response_messages = []
            while len(response) > 0:
                response_messages.append(response[:2000])
                response = response[2000:]
            for response_message in response_messages:
                await message.channel.send(response_message)
        else:
            await message.channel.send(response)

    async def run_system_command(self, message):
        command = message.content[2:]
        logger.info(f"Running system command: {command}")
        command_output = os.popen(command).read()
        if command_output:
            command_output = command_output.replace("```", "")
            command_output = f"```{command_output}```"
            await message.channel.send(command_output)
        else:
            await message.channel.send("No output available.")
        return
