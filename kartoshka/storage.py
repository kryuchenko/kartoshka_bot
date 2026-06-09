import fcntl
import json
import logging
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict

from kartoshka.constants import CANDIDATES_FILE, COUNTER_FILE, USER_DATA_FILE


def atomic_write_json(path: str, payload) -> None:
    """Пишет JSON атомарно: tmp-файл в той же директории + os.replace.

    При внезапной смерти процесса (OOM-kill при MemoryMax, рестарт systemd)
    на диске останется либо старая, либо новая версия файла — но не обрезок,
    который при следующем старте молча превратился бы в пустое состояние.
    """
    dir_ = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(dir=dir_, prefix=os.path.basename(path) + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


@contextmanager
def _candidates_lock():
    """Межпроцессная блокировка candidates.json.

    Кандидатов пишет и живой бот (recruit-хендлер), и one-off скрипты
    (broadcast/жребий) — read-modify-write без лока может потерять отклик.
    """
    lock_path = CANDIDATES_FILE + ".lock"
    with open(lock_path, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


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
    try:
        atomic_write_json(COUNTER_FILE, {"meme_counter": counter})
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

        atomic_write_json(USER_DATA_FILE, serialized_data)
    except Exception as e:
        logging.error(f"Ошибка при сохранении данных пользователей: {e}")


def load_candidates() -> list:
    """Список кандидатов в криптоселектархи (отклики на рассылку)."""
    try:
        with open(CANDIDATES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except Exception as e:
        logging.error(f"Ошибка при загрузке кандидатов: {e}")
        return []


def save_candidates(candidates: list) -> None:
    try:
        atomic_write_json(CANDIDATES_FILE, candidates)
    except Exception as e:
        logging.error(f"Ошибка при сохранении кандидатов: {e}")


def add_candidate(user_id: int, username, first_name, ts: str) -> bool:
    """Добавляет кандидата (идемпотентно). Возвращает True если запись новая.

    Повторный отклик обновляет username/first_name, но сохраняет первый ts.
    Read-modify-write выполняется под межпроцессным локом.
    """
    with _candidates_lock():
        candidates = load_candidates()
        for c in candidates:
            if c["id"] == user_id:
                c["username"] = username
                c["first_name"] = first_name
                save_candidates(candidates)
                return False
        candidates.append({
            "id": user_id,
            "username": username,
            "first_name": first_name,
            "ts": ts,
        })
        save_candidates(candidates)
        return True
