import json
import logging
from datetime import datetime
from typing import Any, Dict

from kartoshka.constants import COUNTER_FILE, USER_DATA_FILE


def load_meme_counter() -> int:
    try:
        with open(COUNTER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return int(data.get("meme_counter", 0))
    except FileNotFoundError:
        return 0
    except Exception as e:
        logging.error(f"Ошибка при загрузке счетчика meme_id: {e}")
        return 0


def save_meme_counter(counter: int):
    data = {"meme_counter": counter}
    try:
        with open(COUNTER_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ошибка при сохранении счетчика meme_id: {e}")


def load_user_data() -> Dict[str, Dict[str, Any]]:
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)

        data = {}
        for uid, ud in raw.items():
            data[uid] = {
                "last_submission": datetime.fromisoformat(ud["last_submission"]) if ud.get("last_submission") else None,
                "rejections": ud.get("rejections", 0),
                "ban_until": datetime.fromisoformat(ud["ban_until"]) if ud.get("ban_until") else None,
            }
        return data
    except FileNotFoundError:
        return {}
    except Exception as e:
        logging.error(f"Ошибка при загрузке данных пользователей: {e}")
        return {}


def save_user_data(data: Dict[str, Dict[str, Any]]):
    try:
        serialized_data = {}
        for uid, ud in data.items():
            serialized_data[uid] = {
                "last_submission": ud["last_submission"].isoformat() if ud["last_submission"] else None,
                "rejections": ud["rejections"],
                "ban_until": ud["ban_until"].isoformat() if ud["ban_until"] else None,
            }

        with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(serialized_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ошибка при сохранении данных пользователей: {e}")
