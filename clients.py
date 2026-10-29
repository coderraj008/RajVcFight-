from pyrogram import Client
from pytgcalls import PyTgCalls

from config import API_HASH, API_ID, BOT_TOKEN, STRING_SESSION

bot = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

assistant = Client(
    "assistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=STRING_SESSION,
)

call = PyTgCalls(assistant)
