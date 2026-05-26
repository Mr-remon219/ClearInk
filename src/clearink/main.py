from anthropic import Anthropic
from dotenv import load_dotenv
import os

from .config import ENV_PATH

load_dotenv(ENV_PATH, override=True)
model = os.getenv("MODEL")
client = Anthropic()

def agent_loop(message: list):
    client.messages.create(
        model=model,
        
        
    )


def main():
    Anthropic()