import base64

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
        
        if "generate" in message.content.lower():
            url = await self.chatgpt.generate(message.content)
            await self.channel.send(url)
            return
        
        try:
            await self.chat(message)
        except Exception as e:
            raise e
    
    async def chat(self, message):
        if self.channel is not None:
            await self.channel.typing()
            history = await self.read_chat()

        response_message = await self.chatgpt.respond(history=history)

        # if the message is too long, send it in chunks
        if len(response_message) > self.message_cutoff:
            for i in range(0, len(response_message), self.message_cutoff):
                await message.channel.send(response_message[i:i+self.message_cutoff])
        else:
            await message.channel.send(response_message)
    
    async def read_chat(self):
        if self.channel is None:
            return
        history = []
        messages = [message async for message in self.channel.history(limit=100)][::-1]
        for message in messages:
            if message.author == self.user:
                history.append({"role": "assistant", "content": message.content})
            else:
                if message.attachments:
                    content = []
                    valid_image_extensions = (".jpg", ".jpeg", ".png", ".gif", ".webp")
                    for attachment in message.attachments:
                        if attachment.filename.endswith(valid_image_extensions):
                            image_url = attachment.url
                            content.append({"type": "image_url", "image_url": image_url})
                    if message.content:
                        content.append({"type": "text", "text": message.content})
                    history.append({"role": "user", "content": content})
                else:
                    history.append({"role": "user", "content": f"[{message.author.name}]: {message.content}"})
        return history
    
    async def send_image(self, data):
        if self.channel is None:
            return
        with open("image.webp", "wb") as f:
            f.write(data)
        await self.channel.send(file=discord.File("image.webp"))
    
    async def handle_command(self, message):
        if message.content.startswith("!help"):
            await message.channel.send("Commands: !image, !forget, !clear")
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
