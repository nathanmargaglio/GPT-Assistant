import re
from concurrent.futures import ThreadPoolExecutor

import openai
from config import OPENAI_API_KEY, get_logger
import tiktoken

logger = get_logger(__name__)

openai.api_key = OPENAI_API_KEY


def get_embedding(text):
    logger.debug(f"OpenAI: Getting embedding for text...")
    return openai.Embedding.create(input=[text], model="text-embedding-ada-002")[
        "data"
    ][0]["embedding"]


def get_importance_of_interaction(message, response):
    logger.debug("OpenAI: Chat Completion (get_importance_of_interaction)")
    importance_response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": "You are a large language model. The following is a snippet of a conversation between a user and a chatbot.",
            },
            {"role": "user", "content": message},
            {"role": "assistant", "content": response},
            {
                "role": "system",
                "content": "Please rate the importance of remembering the above interaction on a scale from 1 to 10 where 1 is trivial and 10 is very important. Only respond with the number, do not add any commentary.",
            },
        ],
        temperature=0,
        n=1,
        max_tokens=100,
    )

    numbers = re.findall(
        r"\b(?:10|[1-9])\b", importance_response.choices[0].message.content
    )
    if numbers:
        return int(numbers[0]) / 10

    print(
        "Error: Could not parse importance of interaction. Defaulting to 3 out of 10."
    )
    return 0.3


def get_importance_of_insight(insight):
    logger.debug("OpenAI: Chat Completion (get_importance_of_insight)")
    importance_response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": "You are a large language model. The following is an insight you gained from of a conversation with a user.",
            },
            {"role": "assistant", "content": insight},
            {
                "role": "system",
                "content": "Please rate the importance of remembering the above insight on a scale from 1 to 10 where 1 is trivial and 10 is very important. Only respond with the number, do not add any commentary.",
            },
        ],
        temperature=0,
        n=1,
        max_tokens=100,
    )

    numbers = re.findall(
        r"\b(?:10|[1-9])\b", importance_response.choices[0].message.content
    )
    if numbers:
        return int(numbers[0]) / 10

    print(
        "Error: Could not parse importance of interaction. Defaulting to 3 out of 10."
    )
    return 0.3


def get_insights(messages):
    logger.debug("OpenAI: Chat Completion (get_insights)")
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages
        + [
            {
                "role": "system",
                "content": 'Please list up to 5 high-level insights you can infer from the above conversation. You must respond in a list format with each insight surrounded by quotes, e.g. ["The user seems...", "The user likes...", "The user is...", ...]',
            }
        ],
        temperature=0.7,
        n=1,
        max_tokens=500,
    )

    # Extract the insights from the string
    insights_list = re.findall(r'"(.*?)"', response.choices[0].message.content)

    insights = []
    futures = []
    with ThreadPoolExecutor() as executor:
        for insight in insights_list:
            futures.append(executor.submit(get_importance_of_insight, insight))

        for insight, future in zip(insights_list, futures):
            importance = future.result()
            insights.append({"content": insight, "importance": importance})

    return insights


# https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
def num_tokens_from_messages(messages, model="gpt-3.5-turbo"):
    """Returns the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        logger.warn("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    if model == "gpt-3.5-turbo":
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo-0301")
    elif model == "gpt-3.5-turbo-16k-0613":
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo")
    elif model == "gpt-4":
        return num_tokens_from_messages(messages, model="gpt-4-0314")
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = (
            4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        )
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif model == "gpt-4-0314":
        tokens_per_message = 3
        tokens_per_name = 1
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
