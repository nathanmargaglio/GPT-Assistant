import json
from pprint import pprint

import openai
import tiktoken

from func import LogQS
from config import OPENAI_API_KEY, get_logger

# logger = get_logger(__name__)

openai.api_key = OPENAI_API_KEY

class ChatGPT:
    def __init__(self):
        self.load_config()
        self.lqs = LogQS()
        self.short_term_memory = []
    
    def load_config(self):
        """
        Loads the configuration for the chatbot from the database.
        """
        self.config = {}
        # gpt-4-0613
        # gpt-3.5-turbo-0613
        # gpt-3.5-turbo-16k-0613
        self.gpt_model = self.config.get("gpt_model", "gpt-4-0613")
        self.temperature = float(self.config.get("temperature", 0.3))
        self.max_response_tokens = int(self.config.get("max_response_tokens", 490))
        self.short_term_memory_max_tokens = int(self.config.get("short_term_memory_max_tokens", 1500))

        self.token_capacity = 4096
        if "32k" in self.gpt_model:
            self.token_capacity = 32768
        elif "16k" in self.gpt_model:
            self.token_capacity = 16384
        elif "gpt-4" in self.gpt_model:
            self.token_capacity = 8192

    async def send_message(self, message, send_image, on_function_call):
        self.load_config()

        self.memorize({"role": "user", "content": message})

        response = openai.ChatCompletion.create(
            model=self.gpt_model,
            messages=self.recall(),
            functions=self.lqs.get_function_schemas(),
            function_call="auto",
        )
        assert isinstance(response, dict)
        response_message = response["choices"][0]["message"]
        response_message = await self.handle_response_message(
            response_message=response_message,
            send_image=send_image,
            on_function_call=on_function_call,
        )
        return response_message["content"]
    
    async def handle_response_message(self, response_message, send_image, on_function_call):
        if response_message.get("function_call"):
            message = await self.handle_function_call(
                message=response_message,
                send_image=send_image,
                on_function_call=on_function_call
            )
        else:
            self.memorize({"role": "assistant", "content": response_message["content"]})
            message = response_message
        return message
    
    async def handle_function_call(self, message, send_image, on_function_call):
        function_name = message["function_call"]["name"]
        function_args = json.loads(message["function_call"]["arguments"])
        explain = function_args.pop("explain", None)
        self.memorize({"role": "assistant", "content": explain})
        await on_function_call(message=explain)

        function_response = self.lqs.call_function(function_name, **function_args)
        if type(function_response) == bytes:
            await send_image(function_response)
            function_response = "Image successfully sent to user."
        self.memorize({"role": "function", "name": function_name, "content": function_response})

        response = openai.ChatCompletion.create(
            model=self.gpt_model,
            messages=self.recall(),
            functions=self.lqs.get_function_schemas(),
            function_call="auto",
        )
        assert isinstance(response, dict)
        return await self.handle_response_message(
            response_message=response["choices"][0]["message"],
            send_image=send_image,
            on_function_call=on_function_call,
        )

    def recall(self):
        messages = [
            {
                "role": "system",
                "content": """
                    You are a large language model designed to help users navigate the LogQS API.
                    LogQS allows users to query and visualize data from ROS bags stored in the cloud.
                    A typical workflow has users listing logs, listing topics from the log,
                    querying records from the topics, and visualizing the results.

                    You have the ability to perform function calls to the API.  You can also chain
                    function calls together.  For example, you can list logs, then list topics from
                    a log, then query records from a topic, then visualize the results, all without
                    explicitly waiting for the user to tell you the next step.  When you make a function
                    call, you can optionally provide an explanation of why you're making the call.  This
                    will be displayed to the user to help them understand your thought process.

                    Users will typically ask you to find records pertaining to one topic, then ask you
                    follow-up information related to another.  For example, I user may ask:

                        "When does the vehicle experience the greatest G-force?"
                    
                    And you may tell them the timestamp of the record with the greatest G-force based on
                    query results from the IMU topics.  The user then may ask:

                        "Show me an image from when that occurred."
                    
                    If this occurs, you need to fetch the timestamp from the Image topic nearest to the
                    timestamp of the record with the greatest G-force.  You can do this by making querying
                    the Image topic based on the timestamp from the first result.  You cannot directly
                    use the timestamp from one topic to reference records from another.
                """
            },
        ]   
        messages.extend(self.short_term_memory)
        print("========================================")
        pprint(self.short_term_memory)
        return messages
    
    def memorize(self, message_data):
        self.short_term_memory.append(message_data)
        while (
            self.num_tokens_from_messages(self.short_term_memory, self.gpt_model)
            > self.short_term_memory_max_tokens
        ):
            self.short_term_memory.pop(0)

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
                num_tokens += len(encoding.encode(value))
                if key == "name":
                    num_tokens += tokens_per_name
        num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
        return num_tokens
