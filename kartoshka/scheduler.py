import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, Dict, Optional

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from kartoshka.constants import MODERATION_FILE, PUBLICATION_FILE
from kartoshka.models import Meme

PublishCallback = Callable[[Meme], Awaitable[None]]


class Scheduler:
    MODERATION_FILE = MODERATION_FILE
    PUBLICATION_FILE = PUBLICATION_FILE

    def __init__(
        self,
        post_frequency_minutes: int,
        bot: Optional[Bot] = None,
        on_publish: Optional[PublishCallback] = None,
    ):
        self.post_frequency_minutes = post_frequency_minutes
        self.bot = bot
        self.on_publish = on_publish
        self.last_published_time = datetime.now(timezone.utc)
        self.pending_memes: Dict[int, Meme] = {}
        self.scheduled_posts = []
        self.load_moderation()
        self.load_publication()

    def get_max_meme_id(self) -> int:
        max_id = 0
        for meme in self.pending_memes.values():
            if meme.meme_id > max_id:
                max_id = meme.meme_id
        for entry in self.scheduled_posts:
            meme_id = entry["meme"].get("meme_id", 0)
            if meme_id > max_id:
                max_id = meme_id
        return max_id

    @staticmethod
    def get_next_allowed_time(dt: datetime) -> datetime:
        if dt.hour < 7:
            return dt.replace(hour=7, minute=0, second=0, microsecond=0)
        return dt

    def save_moderation(self):
        data = {"pending_memes": [m.to_dict() for m in self.pending_memes.values()]}
        try:
            with open(self.MODERATION_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Ошибка при сохранении модерационной очереди: {e}")

    def add_pending(self, meme: Meme) -> None:
        self.pending_memes[meme.meme_id] = meme
        self.save_moderation()

    def resolve(self, meme_id: int) -> None:
        self.pending_memes.pop(meme_id, None)
        self.save_moderation()

    def load_moderation(self):
        try:
            with open(self.MODERATION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            pending_list = data.get("pending_memes", [])
            self.pending_memes = {m["meme_id"]: Meme.from_dict(m) for m in pending_list}
        except FileNotFoundError:
            self.pending_memes = {}
        except Exception as e:
            logging.error(f"Ошибка при загрузке модерационной очереди: {e}")
            self.pending_memes = {}

    def save_publication(self):
        data = {
            "last_published_time": self.last_published_time.isoformat(),
            "queue": self.scheduled_posts,
        }
        try:
            with open(self.PUBLICATION_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Ошибка при сохранении очереди публикации: {e}")

    def load_publication(self):
        try:
            with open(self.PUBLICATION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.last_published_time = datetime.fromisoformat(
                data.get("last_published_time", datetime.now(timezone.utc).isoformat())
            )
            self.scheduled_posts = data.get("queue", [])
            for i, entry in enumerate(sorted(self.scheduled_posts, key=lambda x: datetime.fromisoformat(x["scheduled_time"]))):
                entry_time = datetime.fromisoformat(entry["scheduled_time"])
                if entry_time < self.last_published_time:
                    new_time = self.last_published_time + timedelta(minutes=self.post_frequency_minutes * (i + 1))
                    entry["scheduled_time"] = new_time.isoformat()
            self.scheduled_posts.sort(key=lambda x: datetime.fromisoformat(x["scheduled_time"]))
        except FileNotFoundError:
            self.last_published_time = datetime.now(timezone.utc)
            self.scheduled_posts = []
        except Exception as e:
            logging.error(f"Ошибка при загрузке очереди публикации: {e}")
            self.scheduled_posts = []

    async def schedule(self, meme: Meme):
        now = datetime.now(timezone.utc)
        if self.scheduled_posts:
            last_scheduled = datetime.fromisoformat(self.scheduled_posts[-1]["scheduled_time"])
            base_time = last_scheduled + timedelta(minutes=self.post_frequency_minutes)
            scheduled_time = self.get_next_allowed_time(base_time)
        else:
            base_time = max(now, self.last_published_time + timedelta(minutes=self.post_frequency_minutes))
            scheduled_time = self.get_next_allowed_time(base_time)

        entry = {
            "scheduled_time": scheduled_time.isoformat(),
            "meme": meme.to_publication_dict(),
        }
        self.scheduled_posts.append(entry)
        self.scheduled_posts.sort(key=lambda x: datetime.fromisoformat(x["scheduled_time"]))
        if meme.meme_id in self.pending_memes:
            del self.pending_memes[meme.meme_id]
        self.save_publication()
        self.save_moderation()

        if meme.publish_choice == "user" and meme.user_id is not None and self.bot is not None:
            time_diff = (scheduled_time - now).total_seconds()
            if time_diff < 0:
                time_diff = 0
            hours = int(time_diff // 3600)
            minutes_left = int((time_diff % 3600) // 60)
            time_left_str = f"{hours} ч. {minutes_left} мин." if hours > 0 else f"{minutes_left} мин."

            if meme.user_messages:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text=f"✅ Одбр. {meme.get_vote_summary()} • Публ: {scheduled_time.strftime('%H:%M')} UTC ({time_left_str})",
                        callback_data="noop",
                    )]
                ])

                for chat_id, message_id in meme.user_messages:
                    try:
                        await self.bot.edit_message_reply_markup(
                            chat_id=chat_id, message_id=message_id, reply_markup=keyboard
                        )
                    except Exception as e:
                        logging.error(f"Ошибка при обновлении сообщения для пользователя {chat_id}: {e}")
            else:
                try:
                    await self.bot.send_message(
                        meme.user_id,
                        f"Ваш мем одобрен и теперь ждёт публикации.\n\n"
                        f"Ориентировочное время публикации: {scheduled_time.strftime('%H:%M')} по UTC\n"
                        f"(через {time_left_str}).",
                    )
                except Exception as e:
                    logging.error(f"Не удалось уведомить пользователя {meme.user_id} о планировании: {e}")

    async def run(self):
        while True:
            now = datetime.now(timezone.utc)
            expired = []
            for mem_id, meme in list(self.pending_memes.items()):
                if now - meme.created_time > timedelta(days=3):
                    expired.append(mem_id)
            for mid in expired:
                del self.pending_memes[mid]
                self.save_moderation()

            if self.scheduled_posts:
                self.scheduled_posts.sort(key=lambda x: datetime.fromisoformat(x["scheduled_time"]))
                next_entry = self.scheduled_posts[0]
                next_time = datetime.fromisoformat(next_entry["scheduled_time"])
                if next_time > now:
                    await asyncio.sleep(min((next_time - now).total_seconds(), 10))
                else:
                    self.scheduled_posts.pop(0)
                    self.save_publication()
                    meme_data = next_entry["meme"]
                    meme = Meme.from_dict(meme_data)
                    if self.on_publish is not None:
                        try:
                            await self.on_publish(meme)
                        except Exception as e:
                            logging.error(f"Ошибка в on_publish для мема {meme.meme_id}: {e}")
                    self.last_published_time = datetime.now(timezone.utc)
                    self.save_publication()
            else:
                await asyncio.sleep(10)
