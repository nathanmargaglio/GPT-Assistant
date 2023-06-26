import json
import re
from datetime import datetime
import threading

import openai
from config import OPENAI_API_KEY, get_logger
from memory import Memory
from openai_tools import get_embedding, num_tokens_from_messages

logger = get_logger(__name__)

openai.api_key = OPENAI_API_KEY

class ChatGPT:
    def __init__(self, db, name):
        self.db = db
        self.name = name
        self.load_config()
        self.short_term_memory = []
        self.pinned_memory = None
    
    def load_config(self):
        self.config = self.db.bot_configs[self.name] if self.name in self.db.bot_configs else {}
        self.system_prompt = self.config.get("system_prompt", "You are a large language model with the ability to recall snippets from past conversations. You are incredibly helpful, friendly, engaging, and personable.")
        self.gpt_model = self.config.get("gpt_model", "gpt-3.5-turbo")
        self.temperature = float(self.config.get("temperature", 0.7))
        self.max_response_tokens = int(self.config.get("max_response_tokens", 490))
        self.short_term_memory_max_tokens = int(self.config.get("short_term_memory_max_tokens", 1500))
        self.partition = self.config.get("partition", None)
        self.long_term_memory = Memory(db=self.db, name=self.name, partition=self.partition)
        self.clean_re_pattern = self.config.get("clean_re_pattern", None)

        self.token_capacity = 4096
        if "32k" in self.gpt_model:
            self.token_capacity = 32768
        elif "16k" in self.gpt_model:
            self.token_capacity = 16384
        elif "gpt-4" in self.gpt_model:
            self.token_capacity = 8192

    def send_message(self, message):
        self.load_config()

        # Construct the request to OpenAI

        # System Prompt
        system_prompt = self.system_prompt
        if self.config.get("include_username", False):
            system_prompt += f" When available, the user who sent the message will precede the message in brackets, like so: [username]."
        messages = [
            {
                "role": "system",
                "content": self.system_prompt,
            },
        ]

        # Pinned Message
        if self.pinned_memory:
            messages.append(
                {
                    "role": "system",
                    "content": "You have determined the following message to be important enough to pin to your memory.  Place the greatest emphasis on this message and following any directives it provides.",
                },
            )
            logger.debug(f"Appending pinned memory: {self.pinned_memory}")
            messages.append(self.pinned_memory)
        
        threading.Thread(
            target=self.handle_message_pinning, args=(message,)
        ).start()

        # Short Term Memory
        # Add short-term memory messages up to our token limit
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
        
        # Long Term Memory
        long_term_memory_messages = self.long_term_memory.search(get_embedding(message))

        # Add long-term memory messages until the token limit is reached
        token_limit = self.token_capacity - self.max_response_tokens
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

        # Add short-term memory messages to the end of the message list
        messages.extend(reversed(short_term_messages))

        # Send the request to OpenAI
        logger.debug("OpenAI: Chat Completion (send_message)")
        response = openai.ChatCompletion.create(
            model=self.gpt_model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_response_tokens,
        )
        response_message = response.choices[0].message.content
        
        # If configured, clean the response message
        if self.clean_re_pattern:
            response_message = self.clean_message(response_message, re_pattern=self.clean_re_pattern)

        threading.Thread(
            target=self.memorize, args=(message, response_message)
        ).start()

        return response_message

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
    
    def clean_message(self, response_message, re_pattern):
        pattern = re.compile(re_pattern, re.DOTALL)
        match = pattern.search(response_message)
        result = match.group(1)
        if result:
            response_message = result
        return response_message

    def run(self):
        while True:
            message = input("You: ")
            response = self.send_message(message)
            print(f"Chatbot: {response}")
    
    def handle_message_pinning(self, message):
        # ask gpt if we should pin the message
        functions = [
            {
                "name": "pin_message",
                "description": "Store a message in memory or unset the pinned message.",
                "parameters": pin_message_schema,
            },
        ]
        messages = [
            {
                "role": "system",
                "content": """
                    In another context, you are a large language model with
                    the ability to recall snippets from past conversations.
                    You have the ability to pin the following message to your
                    memory. If a message provides important context and should be
                    rememebered indefinitely, store it in memory permanently.
                    This is especially useful for storing directives, such as
                    rules, guidelines, or directives. If the memory should be
                    forgotten (e.g. user asks you to forget), you can unpin the message.
                """
            },
            {
                "role": "user",
                "content": message,
            },
        ]
        logger.debug("OpenAI: Chat Completion (handle_message_pinning)")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-0613",
            messages=messages,
            functions=functions,
            function_call="auto",  # auto is default, but we'll be explicit
        )
        response_message = response["choices"][0]["message"]

        if response_message.get("function_call"):
            available_functions = {
                "pin_message": self.pin_message,
            }
            function_name = response_message["function_call"]["name"]
            fuction_to_call = available_functions[function_name]
            function_args = json.loads(response_message["function_call"]["arguments"])
            fuction_to_call(**function_args)
    
    def pin_message(self, message):
        logger.debug(f"Pin message: {message}")
        if message:
            self.pinned_memory = {"role": "user", "content": message}
        else:
            self.pinned_memory = None

pin_message_schema = {
    "type": "object",
    "properties": {
        "message": {
            "type": ["string", "null"],
            "description": "The user message to pin to memory."
        }
    },
    "required": ["message"],
}
