from gpt import ChatGPT
from config import GPT_MODEL

if __name__ == "__main__":
    chatgpt = ChatGPT(gpt_model=GPT_MODEL)
    chatgpt.run()
