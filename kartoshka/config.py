import os

from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")
EDITOR_IDS_STR = os.getenv("EDITOR_IDS")
PUBLISH_CHAT_ID = os.getenv("PUBLISH_CHAT_ID")
BOT_NAME = os.getenv("BOT_NAME")
POST_FREQUENCY_MINUTES_STR = os.getenv("POST_FREQUENCY_MINUTES")
CRYPTOSELECTARCHY_STR = os.getenv("CRYPTOSELECTARCHY")
VOTES_TO_APPROVE_STR = os.getenv("VOTES_TO_APPROVE")
VOTES_TO_REJECT_STR = os.getenv("VOTES_TO_REJECT")

_required_env_vars = {
    "BOT_TOKEN": API_TOKEN,
    "EDITOR_IDS": EDITOR_IDS_STR,
    "PUBLISH_CHAT_ID": PUBLISH_CHAT_ID,
    "BOT_NAME": BOT_NAME,
    "POST_FREQUENCY_MINUTES": POST_FREQUENCY_MINUTES_STR,
    "CRYPTOSELECTARCHY": CRYPTOSELECTARCHY_STR,
    "VOTES_TO_APPROVE": VOTES_TO_APPROVE_STR,
    "VOTES_TO_REJECT": VOTES_TO_REJECT_STR,
}
_missing_vars = [k for k, v in _required_env_vars.items() if not v]
if _missing_vars:
    raise ValueError(f"Отсутствуют обязательные переменные окружения: {_missing_vars}")

PUBLISH_CHAT_ID = int(PUBLISH_CHAT_ID)
POST_FREQUENCY_MINUTES = int(POST_FREQUENCY_MINUTES_STR)
CRYPTOSELECTARCHY = CRYPTOSELECTARCHY_STR.lower() == "true"
VOTES_TO_APPROVE = int(VOTES_TO_APPROVE_STR)
VOTES_TO_REJECT = int(VOTES_TO_REJECT_STR)
EDITOR_IDS = [int(x.strip()) for x in EDITOR_IDS_STR.split(",")]
