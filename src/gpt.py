from datetime import datetime
import openai
from config import OPENAI_API_KEY
from memory import Memory
from openai_tools import get_embedding, num_tokens_from_messages
from termcolor import colored

openai.api_key = OPENAI_API_KEY


class ChatGPT:
    def __init__(self, gpt_model):
        self.long_term_memory = Memory()
        self.short_term_memory = []
        self.gpt_model = gpt_model
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

    def send_message(self, message):
        messages = [
            {
                "role": "system",
                "content": f"You are a large language model with the ability to recall snippets from past conversations. You are incredibly helpful, friendly, engaging, and personable.",
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
                num_tokens_from_messages(messages + short_term_messages + temp_msg, self.gpt_model)
                <= token_limit
            ):
                messages.extend(temp_msg)
            else:
                break

        messages.extend(reversed(short_term_messages))

        response = openai.ChatCompletion.create(
            model=self.gpt_model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        self.short_term_memory.append({"role": "user", "content": message})
        self.short_term_memory.append(
            {"role": "assistant", "content": response.choices[0].message.content}
        )

        self.long_term_memory.upload_message_response_pair(
            message, response.choices[0].message.content
        )
        self.long_term_memory.reflect(self.short_term_memory)

        while (
            num_tokens_from_messages(self.short_term_memory, self.gpt_model)
            > self.short_term_memory_max_tokens
        ):
            self.short_term_memory.pop(0)

        return response.choices[0].message.content

    def run(self):
        while True:
            message = input(colored("You: ", "green"))
            response = self.send_message(message)
            print(colored(f"Chatbot: {response}", "cyan"))
