import inspect
import json
from datetime import datetime
from pprint import pprint, pformat

import openai
import tiktoken

from config import OPENAI_API_KEY, get_logger

logger = get_logger(__name__)

openai.api_key = OPENAI_API_KEY

class ChatGPT:
    def __init__(self):
        self.load_config()
        self.short_term_memory = []
    
    def load_config(self):
        self.config = {}
        # gpt-4-1106-preview
        # gpt-4-vision-preview
        # gpt-3.5-turbo-1106
        # self.gpt_model = self.config.get("gpt_model", "gpt-4-1106-preview")
        self.gpt_model = self.config.get("gpt_model", "gpt-4-vision-preview")
        self.messages_max_tokens = int(self.config.get("messages_max_tokens", 10_000))

    async def respond(self, history=[]):
        self.load_config()
        response = openai.chat.completions.create(
            model=self.gpt_model,
            messages=self.construct_messages(history),
            stream=False,
            max_tokens=1000,

        )
        response_choice = response.choices[0]
        response_message = response_choice.message
        return response_message.content
    
    async def generate(self, prompt):
        response = openai.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        image_url = response.data[0].url
        return image_url
    
    def construct_messages(self, history=[]):
        message_token_count = self.num_tokens_from_messages(history, self.gpt_model)
        while (message_token_count > self.messages_max_tokens):
            logger.warning(f"History is too long ({message_token_count}/{self.messages_max_tokens}). Trimming...")
            history.pop(0)
            message_token_count = self.num_tokens_from_messages(history, self.gpt_model)
        
        messages = [
            {
                "role": "system",
                "content": inspect.cleandoc(f"""
                    You are a large language model designed to interact with users on Discord. You're to be zany, ignorant, and humorous.
                    The current UTC time is {datetime.now().isoformat()}.
                    When available, the user who sent the message will precede the message in brackets, like so: [username].
                    If you are referring to a user, do not include the brackets.
                """)
            },
        ]   
        messages.extend(history)
        logger.debug("Messages ========================================")
        logger.debug(pformat(messages))
        return messages

    def num_tokens_from_messages(self, messages, model="gpt-3.5-turbo-0613"):
        """Return the number of tokens used by a list of messages."""
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            print("Warning: model not found. Using cl100k_base encoding.")
            encoding = tiktoken.get_encoding("cl100k_base")
        if model in {
            "gpt-3.5-turbo-0613",
            "gpt-3.5-turbo-16k-0613",
            "gpt-4-0314",
            "gpt-4-32k-0314",
            "gpt-4-0613",
            "gpt-4-32k-0613",
            "gpt-4-1106-preview",
            "gpt-4-vision-preview",
            "gpt-3.5-turbo-1106",
            }:
            tokens_per_message = 3
            tokens_per_name = 1
        elif model == "gpt-3.5-turbo-0301":
            tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
            tokens_per_name = -1  # if there's a name, the role is omitted
        elif "gpt-3.5-turbo-16k" in model:
            return self.num_tokens_from_messages(messages, model="gpt-3.5-turbo-16k-0613")
        elif "gpt-3.5-turbo" in model:
            return self.num_tokens_from_messages(messages, model="gpt-3.5-turbo-0613")
        elif "gpt-4" in model:
            print("Warning: gpt-4 may update over time. Returning num tokens assuming gpt-4-0613.")
            return self.num_tokens_from_messages(messages, model="gpt-4-0613")
        else:
            raise NotImplementedError(
                f"""num_tokens_from_messages() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens."""
            )
        num_tokens = 0
        for message in messages:
            num_tokens += tokens_per_message
            for key, value in message.items():
                if isinstance(value, str):
                    num_tokens += len(encoding.encode(value))
                else:
                    num_tokens += len(encoding.encode(json.dumps(value)))
                if key == "name":
                    num_tokens += tokens_per_name
        num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
        return num_tokens
