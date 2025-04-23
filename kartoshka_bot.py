#!/usr/bin/env python3
import asyncio
import logging
import os
import random
import math
import json
from datetime import datetime, timezone, timedelta
from typing import Union, Optional, Dict
from types import SimpleNamespace

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.client.bot import DefaultBotProperties
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")
EDITOR_IDS_STR = os.getenv("EDITOR_IDS")
PUBLISH_CHAT_ID = os.getenv("PUBLISH_CHAT_ID")
BOT_NAME = os.getenv("BOT_NAME")
POST_FREQUENCY_MINUTES_STR = os.getenv("POST_FREQUENCY_MINUTES")
CRYPTOSELECTARCHY_STR = os.getenv("CRYPTOSELECTARCHY")
VOTES_TO_APPROVE_STR = os.getenv("VOTES_TO_APPROVE")
VOTES_TO_REJECT_STR = os.getenv("VOTES_TO_REJECT")

required_env_vars = {
    "BOT_TOKEN": API_TOKEN,
    "EDITOR_IDS": EDITOR_IDS_STR,
    "PUBLISH_CHAT_ID": PUBLISH_CHAT_ID,
    "BOT_NAME": BOT_NAME,
    "POST_FREQUENCY_MINUTES": POST_FREQUENCY_MINUTES_STR,
    "CRYPTOSELECTARCHY": CRYPTOSELECTARCHY_STR,
    "VOTES_TO_APPROVE": VOTES_TO_APPROVE_STR,
    "VOTES_TO_REJECT": VOTES_TO_REJECT_STR,
}
missing_vars = [k for k, v in required_env_vars.items() if not v]
if missing_vars:
    raise ValueError(f"Отсутствуют обязательные переменные окружения: {missing_vars}")

PUBLISH_CHAT_ID = int(PUBLISH_CHAT_ID)
POST_FREQUENCY_MINUTES = int(POST_FREQUENCY_MINUTES_STR)
CRYPTOSELECTARCHY = CRYPTOSELECTARCHY_STR.lower() == "true"
VOTES_TO_APPROVE = int(VOTES_TO_APPROVE_STR)
VOTES_TO_REJECT = int(VOTES_TO_REJECT_STR)
EDITOR_IDS = [int(x.strip()) for x in EDITOR_IDS_STR.split(",")]

if CRYPTOSELECTARCHY:
    print("Криптоселектархическая олигархия включена! (многоголосие)")
else:
    print("Единоличный Узурпатор у власти! (решение принимает один голос)")

METALS_AND_TOXINS = [
    "Алюминиевой", "Железной", "Медной", "Свинцовой", "Цинковой", "Титановой", "Никелевой",
    "Оксид-железной", "Оксид-цинковой", "Оксид-титановой", "Урановой", "Плутониевой", "Ториевой",
    "Радиевой", "Полониевой", "Актиниевой", "Протактиниевой", "Америциевой", "Кюриевой",
    "Нептуниевой", "Франциевой", "Лоуренсиевой", "Рутениевой", "Цезиевой", "Бериллиевой",
    "Уран-235", "Диоксид-ториевой", "Карбонат-радиевой", "Гексафторид-урановой",
    "Нитрат-ториевой", "Оксид-плутониевой", "Дейтериевой", "Тритиевой", "Цианистой",
    "Рициновой", "Сариновой", "Зомановой", "Ви-Иксной", "Ботулотоксиновой",
    "Стрихнинной", "Фосгеновой", "Диоксиновой", "Тетродоксиновой", "Полониевой-210",
    "Меркуриевой", "Аманитиновой", "Арсеновой", "Талиевой",
    "Метанольной", "Этиленгликолевой", "Трихлорэтиленовой", "Хлориновой",
    "Монооксид-углеродной", "Гексафторовой", "Фторводородной",
    "Бромацетоновой", "Хлорацетоновой", "Карбофосовой", "Хлороформовой", "Барбитуровой",
    "Калий-цианистой", "Метилртутной"
]

# Файл для хранения глобального счетчика meme_id
COUNTER_FILE = "meme_counter.json"

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

# Инициализируем глобальный счетчик
meme_counter = load_meme_counter()

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))

user_publish_choice: Dict[int, str] = {}

def serialize_message(message: Message) -> dict:
    data = {"content_type": message.content_type}
    if message.content_type == "text":
        data["text"] = getattr(message, "text", "")
    elif message.content_type == "photo":
        # Handle None photo case
        photo_list = getattr(message, "photo", None)
        if photo_list is None:
            data["photo"] = []
        else:
            try:
                data["photo"] = [{"file_id": photo.file_id} for photo in photo_list]
            except (AttributeError, TypeError):
                data["photo"] = []
        data["caption"] = getattr(message, "caption", None)
    elif message.content_type == "video":
        try:
            data["video"] = {"file_id": getattr(message.video, "file_id", "")}
        except AttributeError:
            data["video"] = {"file_id": ""}
        data["caption"] = getattr(message, "caption", None)
    elif message.content_type == "animation":
        try:
            data["animation"] = {"file_id": getattr(message.animation, "file_id", "")}
        except AttributeError:
            data["animation"] = {"file_id": ""}
        data["caption"] = getattr(message, "caption", None) 
    elif message.content_type == "voice":
        try:
            data["voice"] = {"file_id": getattr(message.voice, "file_id", "")}
        except AttributeError:
            data["voice"] = {"file_id": ""}
        data["caption"] = getattr(message, "caption", None)
    elif message.content_type == "video_note":
        try:
            data["video_note"] = {"file_id": getattr(message.video_note, "file_id", "")}
        except AttributeError:
            data["video_note"] = {"file_id": ""}
    else:
        data["text"] = getattr(message, "text", "")
    return data

class DummyMessage:
    def __init__(self, data: dict):
        self.content_type = data["content_type"]
        if self.content_type == "text":
            self.text = data.get("text", "")
        elif self.content_type == "photo":
            photo_data = data.get("photo")
            if photo_data is None:
                self.photo = []
            else:
                try:
                    self.photo = [SimpleNamespace(**photo) for photo in photo_data]
                except (TypeError, AttributeError):
                    self.photo = []
            self.caption = data.get("caption")
        elif self.content_type == "video":
            video_data = data.get("video")
            if video_data is None:
                self.video = SimpleNamespace(file_id="")
            else:
                try:
                    self.video = SimpleNamespace(**video_data)
                except (TypeError, AttributeError):
                    self.video = SimpleNamespace(file_id="") 
            self.caption = data.get("caption")
        elif self.content_type == "animation":
            animation_data = data.get("animation")
            if animation_data is None:
                self.animation = SimpleNamespace(file_id="")
            else:
                try:
                    self.animation = SimpleNamespace(**animation_data)
                except (TypeError, AttributeError):
                    self.animation = SimpleNamespace(file_id="")
            self.caption = data.get("caption")
        elif self.content_type == "voice":
            voice_data = data.get("voice")
            if voice_data is None:
                self.voice = SimpleNamespace(file_id="")
            else:
                try:
                    self.voice = SimpleNamespace(**voice_data)
                except (TypeError, AttributeError):
                    self.voice = SimpleNamespace(file_id="")
            self.caption = data.get("caption")
        elif self.content_type == "video_note":
            video_note_data = data.get("video_note")
            if video_note_data is None:
                self.video_note = SimpleNamespace(file_id="")
            else:
                try:
                    # Process nested structures like thumb
                    processed_data = {}
                    for key, value in video_note_data.items():
                        if isinstance(value, dict):
                            processed_data[key] = SimpleNamespace(**value)
                        else:
                            processed_data[key] = value
                    self.video_note = SimpleNamespace(**processed_data)
                except (TypeError, AttributeError):
                    self.video_note = SimpleNamespace(file_id="")
        else:
            self.text = data.get("text", "")

def deserialize_message(data: dict) -> DummyMessage:
    return DummyMessage(data)

AnyMessage = Union[Message, DummyMessage]

async def send_media_message(
    telegram_bot: Bot,
    chat_id: int,
    content: AnyMessage,
    caption: str = None,
    reply_markup=None
):
    if not caption:
        caption = getattr(content, "caption", "") or getattr(content, "text", "")
    caption = caption or ""
    ctype = getattr(content, "content_type", "text")
    if ctype == "photo":
        return await telegram_bot.send_photo(
            chat_id=chat_id,
            photo=content.photo[-1].file_id,
            caption=caption,
            reply_markup=reply_markup
        )
    elif ctype == "video":
        return await telegram_bot.send_video(
            chat_id=chat_id,
            video=content.video.file_id,
            caption=caption,
            reply_markup=reply_markup
        )
    elif ctype == "animation":
        return await telegram_bot.send_animation(
            chat_id=chat_id,
            animation=content.animation.file_id,
            caption=caption,
            reply_markup=reply_markup
        )
    elif ctype == "voice":
        return await telegram_bot.send_voice(
            chat_id=chat_id,
            voice=content.voice.file_id,
            caption=caption,
            reply_markup=reply_markup
        )
    elif ctype == "video_note":
        return await telegram_bot.send_video_note(
            chat_id=chat_id,
            video_note=content.video_note.file_id,
            reply_markup=reply_markup
        )
    else:
        # Всегда используем caption для текстовых сообщений, а не только text
        return await telegram_bot.send_message(
            chat_id=chat_id,
            text=caption,
            reply_markup=reply_markup
        )

class Meme:
    def __init__(
        self,
        meme_id: int,
        user_id: Optional[int],
        publish_choice: str,
        content: AnyMessage
    ):
        # Сохраняем user_id в оперативной памяти (для уведомлений до перезагрузки)
        self.meme_id = meme_id
        self.user_id = user_id  
        self.publish_choice = publish_choice
        self.content = content
        self.votes = {}
        self.mod_messages = []
        self.user_messages = []  # Список сообщений пользователя для обновления
        self.finalized = False
        self.created_time = datetime.now(timezone.utc)

    def add_vote(self, crypto_id: int, vote: str) -> Optional[str]:
        key = str(crypto_id)  # гарантируем, что ключ всегда строка
        prev_vote = self.votes.get(key)
        self.votes[key] = vote
        return prev_vote

    def count_votes(self, vote_type: str) -> int:
        if vote_type == "approve":
            return sum(1 for v in self.votes.values() if v in ("approve", "urgent"))
        return sum(1 for v in self.votes.values() if v == vote_type)

    def is_approved(self) -> bool:
        return self.count_votes("approve") >= VOTES_TO_APPROVE

    def is_urgent(self) -> bool:
        urgent_count = sum(1 for v in self.votes.values() if v == "urgent")
        urgent_threshold = max(1, math.ceil(VOTES_TO_APPROVE * 0.51))
        return urgent_count >= urgent_threshold

    def is_rejected(self) -> bool:
        return self.count_votes("reject") >= VOTES_TO_REJECT

    def get_vote_summary(self) -> str:
        approve_count = sum(1 for v in self.votes.values() if v == "approve")
        urgent_count = sum(1 for v in self.votes.values() if v == "urgent")
        reject_count = sum(1 for v in self.votes.values() if v == "reject")
        return f"(✅ {approve_count} | ⚡ {urgent_count} | ❌ {reject_count})"

    def get_caption(self) -> str:
        user_text = getattr(self.content, "caption", "") or getattr(self.content, "text", "")
        if self.publish_choice == "user":
            prefix = "Мем от пользователя"
        else:
            random_metal = random.choice(METALS_AND_TOXINS)
            plain_prefix = f"Мем от Анонимной {random_metal} Картошки"
            prefix = f"<tg-spoiler>{plain_prefix}</tg-spoiler>"
        
        # Всегда возвращаем подпись с префиксом, даже если пользовательский текст пустой
        return f"{prefix}\n\n{user_text}" if user_text else f"{prefix}"

    def to_dict(self) -> dict:
        # Для модерации сохраняем полную информацию, включая голоса.
        # Для анонимных (potato) не сохраняем user_id.
        meme_dict = {
            "meme_id": self.meme_id,
            "publish_choice": self.publish_choice,
            "content": serialize_message(self.content),
            "created_time": self.created_time.isoformat(),
            "votes": self.votes
        }
        if self.publish_choice != "potato":
            meme_dict["user_id"] = self.user_id
        return meme_dict

    def to_publication_dict(self) -> dict:
        meme_dict = {
            "meme_id": self.meme_id,
            "publish_choice": self.publish_choice,
            "content": serialize_message(self.content),
            "created_time": self.created_time.isoformat()
        }
        if self.publish_choice != "potato":
            meme_dict["user_id"] = self.user_id
        return meme_dict

    @staticmethod
    def from_dict(d: dict) -> "Meme":
        content = deserialize_message(d["content"])
        meme = Meme(
            meme_id=d["meme_id"],
            user_id=None,  # При загрузке из файлов user_id не восстанавливается
            publish_choice=d["publish_choice"],
            content=content
        )
        meme.created_time = datetime.fromisoformat(d["created_time"])
        meme.votes = d.get("votes", {})
        return meme

class Scheduler:
    MODERATION_FILE = "moderation_queue.json"
    PUBLICATION_FILE = "publication_queue.json"

    def __init__(self, post_frequency_minutes: int):
        self.post_frequency_minutes = post_frequency_minutes
        self.last_published_time = datetime.now(timezone.utc)
        self.pending_memes: Dict[int, Meme] = {}
        self.scheduled_posts = []
        self.load_moderation()
        self.load_publication()
        global meme_counter
        meme_counter = self.get_max_meme_id()

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
            "queue": self.scheduled_posts
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
                    new_time = self.last_published_time + timedelta(minutes=self.post_frequency_minutes*(i+1))
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
            "meme": meme.to_publication_dict()
        }
        self.scheduled_posts.append(entry)
        self.scheduled_posts.sort(key=lambda x: datetime.fromisoformat(x["scheduled_time"]))
        if meme.meme_id in self.pending_memes:
            del self.pending_memes[meme.meme_id]
        self.save_publication()
        self.save_moderation()

        if meme.publish_choice == "user" and meme.user_id is not None:
            time_diff = (scheduled_time - now).total_seconds()
            if time_diff < 0:
                time_diff = 0
            hours = int(time_diff // 3600)
            minutes_left = int((time_diff % 3600) // 60)
            time_left_str = f"{hours} ч. {minutes_left} мин." if hours > 0 else f"{minutes_left} мин."
            
            # Если есть пользовательский виджет, обновляем его с информацией о запланированной публикации
            if meme.user_messages:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text=f"✅ Одобрен {meme.get_vote_summary()} • Публикация: {scheduled_time.strftime('%H:%M')} UTC (через {time_left_str})", 
                        callback_data="noop"
                    )]
                ])
                
                for chat_id, message_id in meme.user_messages:
                    try:
                        await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=keyboard)
                    except Exception as e:
                        logging.error(f"Ошибка при обновлении сообщения для пользователя {chat_id}: {e}")
            # Если нет виджета, отправляем обычное сообщение
            else:
                await bot.send_message(
                    meme.user_id,
                    f"Ваш мем одобрен и теперь ждёт публикации.\n\n"
                    f"Ориентировочное время публикации: {scheduled_time.strftime('%H:%M')} по UTC\n"
                    f"(через {time_left_str})."
                )

    async def run(self):
        while True:
            now = datetime.now(timezone.utc)
            # Удаляем заявки, которым больше 3 дней
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
                    await publish_meme(meme)
                    self.last_published_time = datetime.now(timezone.utc)
                    self.save_publication()
            else:
                await asyncio.sleep(10)

async def update_mod_messages_with_resolution(meme: Meme, resolution: str):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=resolution, callback_data="noop")]
    ])
    for chat_id, message_id in meme.mod_messages:
        try:
            await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=keyboard)
        except Exception as e:
            logging.error(f"Ошибка при обновлении сообщения для редактора {chat_id}: {e}")

async def update_user_messages_with_status(meme: Meme, final_resolution: str = None):
    """Обновляет сообщения пользователя с текущей статистикой голосования"""
    if meme.user_id is None or not meme.user_messages:
        return  # Если нет пользователя или его сообщений, ничего не делаем
    
    vote_summary = meme.get_vote_summary()
    
    # Если голосование завершено, показываем финальное решение
    if final_resolution:
        status_text = f"{final_resolution} {vote_summary}"
    else:
        # Иначе показываем текущую статистику
        status_text = f"Голосование: {vote_summary}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=status_text, callback_data="noop")]
    ])
    
    for chat_id, message_id in meme.user_messages:
        try:
            await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=keyboard)
        except Exception as e:
            logging.error(f"Ошибка при обновлении сообщения для пользователя {chat_id}: {e}")

async def publish_meme(meme: Meme):
    try:
        # Всегда передаем caption явно для правильной подписи
        caption = meme.get_caption()
        await send_media_message(
            telegram_bot=bot,
            chat_id=PUBLISH_CHAT_ID,
            content=meme.content,
            caption=caption
        )
    except Exception as e:
        logging.error(f"Ошибка при публикации: {e}")

scheduler = Scheduler(POST_FREQUENCY_MINUTES)

async def main():
    global meme_counter
    dp = Dispatcher()

    @dp.message(Command("start"))
    async def cmd_start(message: Message):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 От своего имени.", callback_data="choice_user")],
            [InlineKeyboardButton(text="🥔 Анонимно (от «Картошки»).", callback_data="choice_potato")]
        ])
        if CRYPTOSELECTARCHY:
            intro_text = (
                f"Привет! Я {BOT_NAME}.\n\n"
                "Да здравствует Криптоселектархическая олигархия!\n"
                "Решения принимаются коллективно.\n\n"
                "Как вы хотите опубликовать мем?"
            )
        else:
            intro_text = (
                f"Привет! Я {BOT_NAME}.\n\n"
                "Единоличный Узурпатор у власти.\n"
                "Как вы хотите опубликовать мем?"
            )
        await message.answer(intro_text, reply_markup=keyboard)

    @dp.callback_query(F.data.in_(["choice_user", "choice_potato"]))
    async def handle_choice(callback: CallbackQuery):
        user_id = callback.from_user.id
        if callback.data == "choice_user":
            user_publish_choice[user_id] = "user"
            await callback.message.answer("Буду публиковать от вашего имени. Пришлите мем.")
        else:
            user_publish_choice[user_id] = "potato"
            await callback.message.answer("Буду публиковать анонимно (от 'Картошки'). Пришлите мем.")
        await callback.answer()

    @dp.message(F.content_type.in_(["text", "photo", "video", "animation", "voice", "video_note"]))
    async def handle_meme_suggestion(message: Message):
        user_id = message.from_user.id
        if user_id not in user_publish_choice:
            await message.answer("Сначала выберите способ публикации с помощью команды /start.")
            return

        global meme_counter
        meme_counter += 1
        chosen_mode = user_publish_choice[user_id]
        real_user_id: Optional[int] = user_id

        meme = Meme(
            meme_id=meme_counter,
            user_id=real_user_id,
            publish_choice=chosen_mode,
            content=message
        )
        scheduler.pending_memes[meme.meme_id] = meme
        scheduler.save_moderation()
        save_meme_counter(meme_counter)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅Одобр.", callback_data=f"approve_{meme.meme_id}"),
                InlineKeyboardButton(text="⚡Срочно⚡", callback_data=f"urgent_{meme.meme_id}"),
                InlineKeyboardButton(text="❌Отклонить", callback_data=f"reject_{meme.meme_id}")
            ]
        ])

        # Если мем от неанонимного пользователя, показываем username (если есть) или ID;
        # если мем от анонима, то выводим "Картошка"
        if chosen_mode == "user":
            if message.from_user.username:
                from_text = f"@{message.from_user.username}"
            else:
                from_text = f"{message.from_user.id}"
        else:
            from_text = "Картошка"

        user_text = message.caption if message.caption else message.text
        info_text = (
            f"Мем ID: {meme.meme_id}\n\n{user_text}\n\nОт: {from_text}\n"
            f"Публикация как: {chosen_mode}"
        )

        for crypto_id in EDITOR_IDS:
            try:
                sent_msg = await send_media_message(
                    telegram_bot=bot,
                    chat_id=crypto_id,
                    content=message,
                    caption=info_text,
                    reply_markup=keyboard
                )
                meme.mod_messages.append((crypto_id, sent_msg.message_id))
            except Exception as e:
                logging.error(f"Не удалось отправить сообщение редактору {crypto_id}: {e}")

        # Отправляем пользователю сообщение с начальной статистикой и сохраняем его для обновления
        user_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"Голосование: {meme.get_vote_summary()}", callback_data="noop")]
        ])
        user_msg = await message.answer("Ваш мем отправлен на модерацию.", reply_markup=user_keyboard)
        
        # Сохраняем сообщение пользователя для обновления
        if meme.user_id is not None:
            meme.user_messages.append((meme.user_id, user_msg.message_id))

    @dp.callback_query(F.data.startswith(("approve_", "urgent_", "reject_")))
    async def crypto_callback(callback: CallbackQuery):
        data = callback.data
        action, meme_id_str = data.split("_", 1)
        meme_id = int(meme_id_str)
        if meme_id not in scheduler.pending_memes:
            await callback.answer("Заявка не найдена или уже обработана.")
            return

        meme = scheduler.pending_memes[meme_id]
        crypto_id = callback.from_user.id
        prev_vote = meme.add_vote(crypto_id, action)
        scheduler.save_moderation()

        # Вместо отправки множества сообщений, обновляем виджет статистики голосов у пользователя
        await update_user_messages_with_status(meme)

        await callback.answer("Ваш голос учтен.", show_alert=False)

        if not CRYPTOSELECTARCHY:
            if action in ("approve", "urgent"):
                if action == "urgent":
                    resolution = "⚡ Одобрен срочно"
                    await publish_meme(meme)
                    # Обновляем статус пользовательского виджета с финальным решением без лишних сообщений
                    await update_user_messages_with_status(meme, "⚡ Одобрен срочно")
                else:
                    resolution = "✅ Одобрен"
                    await scheduler.schedule(meme)
                    # Обновляем статус пользовательского виджета с финальным решением без лишних сообщений
                    await update_user_messages_with_status(meme, "✅ Одобрен")
            else:
                resolution = "❌ Отклонён"
                # Обновляем статус пользовательского виджета с финальным решением без лишних сообщений
                await update_user_messages_with_status(meme, "❌ Отклонён")
            meme.finalized = True
            resolution_with_summary = f"{resolution} {meme.get_vote_summary()}"
            await update_mod_messages_with_resolution(meme, resolution_with_summary)
            del scheduler.pending_memes[meme.meme_id]
            scheduler.save_moderation()
            return

        if meme.is_approved() and not meme.finalized:
            if meme.is_urgent():
                resolution = "⚡ Одобрен срочно"
                await publish_meme(meme)
                # Обновляем статус пользовательского виджета с финальным решением без лишних сообщений
                await update_user_messages_with_status(meme, "⚡ Одобрен срочно")
            else:
                resolution = "✅ Одобрен"
                await scheduler.schedule(meme)
                # Обновляем статус пользовательского виджета с финальным решением без лишних сообщений
                await update_user_messages_with_status(meme, "✅ Одобрен")
            meme.finalized = True
            resolution_with_summary = f"{resolution} {meme.get_vote_summary()}"
            await update_mod_messages_with_resolution(meme, resolution_with_summary)
            del scheduler.pending_memes[meme.meme_id]
            scheduler.save_moderation()
            return

        if meme.is_rejected() and not meme.finalized:
            resolution = "❌ Отклонён"
            # Обновляем статус пользовательского виджета с финальным решением без лишних сообщений
            await update_user_messages_with_status(meme, "❌ Отклонён")
            meme.finalized = True
            resolution_with_summary = f"{resolution} {meme.get_vote_summary()}"
            await update_mod_messages_with_resolution(meme, resolution_with_summary)
            del scheduler.pending_memes[meme.meme_id]
            scheduler.save_moderation()

    @dp.callback_query(lambda c: c.data == "noop")
    async def noop_callback(callback: CallbackQuery):
        await callback.answer("Голосование завершено, эта кнопка не активна.", show_alert=True)

    asyncio.create_task(scheduler.run())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
