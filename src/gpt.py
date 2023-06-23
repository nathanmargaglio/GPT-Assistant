import sys
from datetime import datetime
import logging
import threading

import openai
from config import OPENAI_API_KEY, LOG_LEVEL, LOG_TO_FILE
from memory import Memory
from openai_tools import get_embedding, num_tokens_from_messages

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

openai.api_key = OPENAI_API_KEY


class ChatGPT:
    def __init__(self, db, name):
        self.db = db
        self.name = name
        self.load_config()

        self.long_term_memory = Memory(db=self.db, name=self.name)
        self.short_term_memory = []
        self.max_tokens = 500
        self.short_term_memory_max_tokens = 1500
        self.temperature = 0.7
        self.token_capacity = 4096
        if "32k" in self.gpt_model:
            self.token_capacity = 32768
        elif "16k" in self.gpt_model:
            self.token_capacity = 16384
        elif "gpt-4" in self.gpt_model:
            self.token_capacity = 8192
    
    def load_config(self):
        self.config = self.db.bot_configs[self.name] if self.name in self.db.bot_configs else {}
        self.system_prompt = (
            self.config["system_prompt"]
            if "system_prompt" in self.config
            else "You are a large language model with the ability to recall snippets from past conversations. You are incredibly helpful, friendly, engaging, and personable."
        )
        self.gpt_model = (
            self.config["gpt_model"]
            if "gpt_model" in self.config
            else "gpt-3.5-turbo-16k-0613"
        )

    def send_message(self, message):
        self.load_config()
        system_prompt = self.system_prompt
        if self.config.get("include_username", False):
            system_prompt += f" When available, the user who sent the message will precede the message in brackets, like so: [username]."
        messages = [
            {
                "role": "system",
                "content": self.system_prompt,
            },
        ]

        long_term_memory_messages = self.long_term_memory.search(get_embedding(message))

        # Add short-term memory messages up to 1500 tokens
        short_term_messages = [
            {
                "role": "system",
                "content": f"Current UTC time: {datetime.now().isoformat()}",
            },
            {"role": "user", "content": message},
        ]
        for msg in reversed(self.short_term_memory):
            if (
                num_tokens_from_messages(short_term_messages + [msg], self.gpt_model)
                <= self.short_term_memory_max_tokens
            ):
                short_term_messages.append(msg)
            else:
                break

        # Add long-term memory messages until the token limit is reached
        token_limit = self.token_capacity - self.max_tokens
        for msg in sorted(long_term_memory_messages, key=lambda x: x["timestamp"]):
            if msg["insight"]:
                temp_msg = [
                    {
                        "role": "system",
                        "content": f"You had the following insight on {msg['timestamp']}: {msg['insight']}",
                    }
                ]
            else:
                temp_msg = [
                    {
                        "role": "system",
                        "content": f"This is a snippet from earlier on {msg['timestamp']}",
                    },
                    {"role": "user", "content": msg["message"]},
                    {"role": "assistant", "content": msg["response"]},
                ]

            if (
                num_tokens_from_messages(
                    messages + short_term_messages + temp_msg, self.gpt_model
                )
                <= token_limit
            ):
                messages.extend(temp_msg)
            else:
                break

        messages.extend(reversed(short_term_messages))

        logger.debug("OpenAI: Chat Completion (send_message)")
        response = openai.ChatCompletion.create(
            model=self.gpt_model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        threading.Thread(
            target=self.memorize, args=(message, response.choices[0].message.content)
        ).start()

        return response.choices[0].message.content

    def memorize(self, message, response_content):
        self.short_term_memory.append({"role": "user", "content": message})
        self.short_term_memory.append(
            {"role": "assistant", "content": response_content}
        )
        while (
            num_tokens_from_messages(self.short_term_memory, self.gpt_model)
            > self.short_term_memory_max_tokens
        ):
            self.short_term_memory.pop(0)

        self.long_term_memory.upload_message_response_pair(message, response_content)
        self.long_term_memory.reflect(self.short_term_memory)

    def run(self):
        while True:
            message = input("You: ")
            response = self.send_message(message)
            print(f"Chatbot: {response}")
