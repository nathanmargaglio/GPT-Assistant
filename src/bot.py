from config import get_logger

logger = get_logger(__name__)

import discord
from gpt import ChatGPT

class BotClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chatgpt = ChatGPT()
        self.message_cutoff = 1995
        self.channel = None
    
    async def on_ready(self):
        logger.info(f"Logged on as {self.user}")
    
    async def on_message(self, message):
        if message.channel.id == 1151634931232034907:
            if self.channel is None:
                self.channel = message.channel
        else:
            return
        
        logger.info(f"> {message.author} ({message.channel.id}): {message.content}")

        if message.author == self.user:
            return
        
        if message.content.startswith("!"):
            await self.handle_command(message)
            return
        
        try:
            await self.chat(message)
        except Exception as e:
            raise e
    
    async def on_function_call(self, message=None):
        if self.channel is None:
            return
        if message is not None:
            await self.channel.send(message[:self.message_cutoff])
        await self.channel.typing()
    
    async def chat(self, message):
        if self.channel is not None:
            await self.channel.typing()
        response_message = await self.chatgpt.send_message(
            message.content,
            send_image=self.send_image,
            on_function_call=self.on_function_call
        )
        await message.channel.send(response_message[:self.message_cutoff])
    
    async def send_image(self, data):
        if self.channel is None:
            return
        with open("image.webp", "wb") as f:
            f.write(data)
        await self.channel.send(file=discord.File("image.webp"))
    
    async def handle_command(self, message):
        if message.content.startswith("!help"):
            await message.channel.send("Commands: !image, !froget, !clear")
        elif message.content.startswith("!image"):
            if self.channel is None:
                return
            await self.channel.send(file=discord.File("bobby.png"))
        elif message.content.startswith("!forget"):
            self.chatgpt.short_term_memory = []
            await message.channel.send("Memory cleared.")
        elif message.content.startswith("!clear"):
            if self.channel is None:
                return
            await message.channel.send("Clearing chat history...")
            await self.channel.purge(limit=100)
