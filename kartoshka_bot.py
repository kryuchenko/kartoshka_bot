import asyncio
import logging
import os
import random
import math
from datetime import datetime, timezone, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from dotenv import load_dotenv
from aiogram.client.bot import DefaultBotProperties

logging.basicConfig(level=logging.INFO)

# Загружаем переменные из файла .env
load_dotenv()

# Получаем значения переменных окружения (как есть, без преобразования)
API_TOKEN = os.getenv("BOT_TOKEN")
EDITOR_IDS_STR = os.getenv("EDITOR_IDS")
PUBLISH_CHAT_ID = os.getenv("PUBLISH_CHAT_ID")
BOT_NAME = os.getenv("BOT_NAME")
POST_FREQUENCY_MINUTES_STR = os.getenv("POST_FREQUENCY_MINUTES")
CRYPTOSELECTARCHY_STR = os.getenv("CRYPTOSELECTARCHY")
VOTES_TO_APPROVE_STR = os.getenv("VOTES_TO_APPROVE")
VOTES_TO_REJECT_STR = os.getenv("VOTES_TO_REJECT")

# Добавляем проверку обязательных переменных окружения
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

# После проверки преобразуем значения в нужные типы
PUBLISH_CHAT_ID = int(PUBLISH_CHAT_ID)
POST_FREQUENCY_MINUTES = int(POST_FREQUENCY_MINUTES_STR)
CRYPTOSELECTARCHY = CRYPTOSELECTARCHY_STR.lower() == "true"
VOTES_TO_APPROVE = int(VOTES_TO_APPROVE_STR)
VOTES_TO_REJECT = int(VOTES_TO_REJECT_STR)
EDITOR_IDS = [int(x.strip()) for x in EDITOR_IDS_STR.split(",")]

# Сообщение о режиме работы
if CRYPTOSELECTARCHY:
    print("Криптоселектархическая олигархия включена! Власть принадлежит тайному совету мудрецов.")
else:
    print("Единоличный Узурпатор у власти. Все решения принимает один человек.")

# Список металлов и токсинов (пример)
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

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))

# Словарь для хранения выбора пользователя (от имени или анонимно)
user_publish_choice = {}


# ----------- Универсальная функция отправки медиа или текста -----------
async def send_media_message(
    telegram_bot: Bot,
    chat_id: int,
    content: Message,
    caption: str = None,
    reply_markup=None
):
    """
    Универсальная функция для отправки различных типов контента (фото/видео/гиф и т.д.).
    content: исходное Message от пользователя.
    caption: текст, который нужно вставить (если нет, берётся из content).
    reply_markup: кнопки для сообщения (если нужны).

    Возвращает отправленное сообщение (объект Message).
    """
    # Если не передана caption, берём её из исходного сообщения
    if not caption:
        caption = content.caption if content.caption else content.text
    caption = caption or ""  # чтобы не было None

    if content.photo:
        return await telegram_bot.send_photo(
            chat_id=chat_id,
            photo=content.photo[-1].file_id,
            caption=caption,
            reply_markup=reply_markup
        )
    elif content.video:
        return await telegram_bot.send_video(
            chat_id=chat_id,
            video=content.video.file_id,
            caption=caption,
            reply_markup=reply_markup
        )
    elif content.animation:
        return await telegram_bot.send_animation(
            chat_id=chat_id,
            animation=content.animation.file_id,
            caption=caption,
            reply_markup=reply_markup
        )
    elif content.voice:
        return await telegram_bot.send_voice(
            chat_id=chat_id,
            voice=content.voice.file_id,
            caption=caption,
            reply_markup=reply_markup
        )
    elif content.video_note:
        return await telegram_bot.send_video_note(
            chat_id=chat_id,
            video_note=content.video_note.file_id,
            reply_markup=reply_markup
        )
    else:
        return await telegram_bot.send_message(
            chat_id=chat_id,
            text=caption,
            reply_markup=reply_markup
        )


# ----------- Класс для хранения мема -----------
class Meme:
    def __init__(self, meme_id: int, user_id: int, publish_choice: str, content: Message):
        self.meme_id = meme_id
        self.user_id = user_id
        self.publish_choice = publish_choice
        self.content = content
        self.votes = {}  # криптоселектарх_id -> "approve", "urgent" или "reject"
        self.mod_messages = []  # список кортежей (chat_id, message_id)

    def add_vote(self, crypto_id: int, vote: str) -> str:
        """Добавляет или обновляет голос криптоселектарха и возвращает предыдущий голос (если был)."""
        prev_vote = self.votes.get(crypto_id)
        self.votes[crypto_id] = vote
        return prev_vote

    def count_votes(self, vote_type: str) -> int:
        if vote_type == "approve":
            # Суммируем обычные голоса "approve" и "urgent"
            return sum(1 for v in self.votes.values() if v in ("approve", "urgent"))
        return sum(1 for v in self.votes.values() if v == vote_type)

    def is_approved(self) -> bool:
        """
        Возвращает True, если общее число голосов (approve + urgent) достигло значения VOTES_TO_APPROVE.
        """
        total_approves = self.count_votes("approve")
        return total_approves >= VOTES_TO_APPROVE

    def is_urgent(self) -> bool:
        """
        Возвращает True, если число голосов "urgent" не меньше 51% от VOTES_TO_APPROVE.
        Например, при VOTES_TO_APPROVE = 3 необходимо минимум math.ceil(3*0.51)=2 срочных голоса.
        """
        urgent_count = self.count_votes("urgent")
        urgent_threshold = math.ceil(VOTES_TO_APPROVE * 0.51)
        return urgent_count >= urgent_threshold

    def is_rejected(self) -> bool:
        return self.count_votes("reject") >= VOTES_TO_REJECT

    def get_caption(self) -> str:
        """Формируем текст сообщения (caption или text) вместе с префиксом.
           Если публикация анонимная, префикс скрывается спойлером."""
        user_text = self.content.caption if self.content.caption else self.content.text

        if self.publish_choice == "user":
            prefix = f"Мем от @{self.content.from_user.username or self.user_id}"
        else:
            random_metal = random.choice(METALS_AND_TOXINS)
            plain_prefix = f"Мем от Анонимной {random_metal} Картошки"
            prefix = f"<tg-spoiler>{plain_prefix}</tg-spoiler>"

        if user_text:
            return f"{prefix}\n\n{user_text}"
        else:
            return prefix


# ----------- Планировщик публикации -----------
class Scheduler:
    def __init__(self, post_frequency_minutes: int):
        self.post_frequency_minutes = post_frequency_minutes
        # Используем min с tz=UTC, чтобы объект был timezone-aware
        self.last_published_time = datetime.min.replace(tzinfo=timezone.utc)
        self.scheduled_posts = []  # список кортежей (scheduled_time, meme)

    async def schedule(self, meme: Meme):
        # Берём текущее время с учётом UTC
        now = datetime.now(timezone.utc)
        next_possible_time = self.last_published_time + timedelta(minutes=self.post_frequency_minutes)

        # Если можем опубликовать немедленно и нет очереди
        if now >= next_possible_time and not self.scheduled_posts:
            await publish_meme(meme)
            self.last_published_time = datetime.now(timezone.utc)
            await bot.send_message(meme.user_id, "Ваш мем одобрен и опубликован немедленно!")
        else:
            # Определяем время публикации этого мема
            if self.scheduled_posts:
                last_scheduled_time = self.scheduled_posts[-1][0]
                scheduled_time = last_scheduled_time + timedelta(minutes=self.post_frequency_minutes)
            else:
                scheduled_time = next_possible_time

            self.scheduled_posts.append((scheduled_time, meme))
            self.scheduled_posts.sort(key=lambda x: x[0])

            # Расчёт оставшегося времени
            time_diff = (scheduled_time - now).total_seconds()
            if time_diff < 0:
                time_diff = 0

            hours = int(time_diff // 3600)
            minutes_left = int((time_diff % 3600) // 60)

            if hours > 0:
                time_left_str = f"{hours} ч. {minutes_left} мин."
            else:
                time_left_str = f"{minutes_left} мин."

            await bot.send_message(
                meme.user_id,
                f"Ваш мем одобрен и теперь ждёт очереди на публикацию.\n\n"
                f"Ориентировочное время публикации: {scheduled_time.strftime('%H:%M')} по UTC\n"
                f"(через {time_left_str})."
            )

    async def run(self):
        while True:
            now = datetime.now(timezone.utc)
            if self.scheduled_posts:
                self.scheduled_posts.sort(key=lambda x: x[0])
                next_time, meme = self.scheduled_posts[0]
                wait_seconds = (next_time - now).total_seconds()

                if wait_seconds > 0:
                    # Спим либо до публикации, либо 10 секунд для проверки
                    await asyncio.sleep(min(wait_seconds, 10))
                else:
                    self.scheduled_posts.pop(0)
                    await publish_meme(meme)
                    self.last_published_time = datetime.now(timezone.utc)
            else:
                await asyncio.sleep(10)


# ----------- Удаление кнопок у криптоселектархов -----------
async def remove_voting_buttons(meme: Meme):
    for chat_id, message_id in meme.mod_messages:
        try:
            await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=None)
        except Exception as e:
            logging.error(f"Ошибка при удалении кнопок у криптоселектарха {chat_id}: {e}")


# ----------- Публикация мема в конечный чат -----------
async def publish_meme(meme: Meme):
    try:
        await send_media_message(
            telegram_bot=bot,  # параметр telegram_bot
            chat_id=PUBLISH_CHAT_ID,
            content=meme.content,
            caption=meme.get_caption()
        )
    except Exception as e:
        logging.error(f"Ошибка при публикации: {e}")


# Глобальные структуры для хранения мема
pending_memes = {}
meme_counter = 0
scheduler = Scheduler(POST_FREQUENCY_MINUTES)


# ----------- Точка входа и настройка Dispatcher -----------
async def main():
    dp = Dispatcher()

    @dp.message(Command("start"))
    async def cmd_start(message: Message):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 От своего имени.", callback_data="choice_user")],
            [InlineKeyboardButton(text="🥔 Анонимно (от «Картошки»).", callback_data="choice_potato")]
        ])

        if CRYPTOSELECTARCHY:
            intro_text = (
                f"Привет! Я бот {BOT_NAME}.\n\n"
                "Ура! Свершилось! Гадкий Узурпатор канул в небытие, и теперь наступила эпоха "
                "Криптоселектархической олигархии!\n"
                "Решения теперь принимаются коллективно тайно отобранными правителями.\n"
                "Как вы хотите опубликовать мем?"
            )
        else:
            intro_text = (
                f"Привет! Я {BOT_NAME}.\n\n"
                "Сейчас ещё не наступила Криптоселектархическая олигархия.\n"
                "Во власти находится Единоличный Узурпатор, но не переживайте! "
                "Когда-нибудь он отойдёт от власти и передаст её группе мудрых Криптоселектархов.\n\n"
                "Как вы хотите опубликовать мем?"
            )
        await message.answer(intro_text, reply_markup=keyboard)

    @dp.callback_query(F.data.in_(["choice_user", "choice_potato"]))
    async def handle_choice(callback: CallbackQuery):
        user_id = callback.from_user.id
        if callback.data == "choice_user":
            user_publish_choice[user_id] = "user"
            await callback.message.answer(
                "Буду публиковать от вашего имени. Пришлите мем (текст/фото/видео/gif, голосовое или видео-заметку)."
            )
        else:
            user_publish_choice[user_id] = "potato"
            await callback.message.answer(
                "Буду публиковать анонимно (от имени «Картошки»). Пришлите мем (текст/фото/видео/gif, голосовое или видео-заметку)."
            )
        await callback.answer()

    @dp.message(F.content_type.in_(["text", "photo", "video", "animation", "voice", "video_note"]))
    async def handle_meme_suggestion(message: Message):
        user_id = message.from_user.id
        if user_id not in user_publish_choice:
            await message.answer("Сначала выберите способ публикации с помощью команды /start.")
            return

        global meme_counter
        meme_counter += 1
        meme = Meme(meme_counter, user_id, user_publish_choice[user_id], message)
        pending_memes[meme.meme_id] = meme

        # Формируем кнопки для криптоселектархов
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅Одобрить", callback_data=f"approve_{meme.meme_id}"),
                InlineKeyboardButton(text="⚡Срочно Одобрить⚡", callback_data=f"urgent_{meme.meme_id}"),
                InlineKeyboardButton(text="❌Отклонить", callback_data=f"reject_{meme.meme_id}")
            ]
        ])

        # Формирование текста для криптоселектархов
        from_text = (
            f"От @{message.from_user.username or user_id}"
            if user_publish_choice[user_id] == "user"
            else "От Анонимного пользователя"
        )
        user_text = message.caption if message.caption else message.text
        info_text = (
            f"Мем ID: {meme.meme_id}\n\n{user_text}\n\n{from_text}\n"
            f"Публикация как: {user_publish_choice[user_id]}"
        )

        # Отправка сообщения всем криптоселектархам
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
                logging.error(f"Не удалось отправить сообщение криптоселектарху {crypto_id}: {e}")

        await message.answer("Ваш мем отправлен на модерацию.")

    @dp.callback_query(F.data.startswith(("approve_", "urgent_", "reject_")))
    async def crypto_callback(callback: CallbackQuery):
        data = callback.data
        action, meme_id_str = data.split("_", 1)
        meme_id = int(meme_id_str)
        if meme_id not in pending_memes:
            await callback.answer("Заявка не найдена или уже обработана.")
            return

        meme = pending_memes[meme_id]
        crypto_id = callback.from_user.id

        # Добавляем голос криптоселектарха и получаем предыдущий голос (если был)
        prev_vote = meme.add_vote(crypto_id, action)

        # Формируем ответ пользователю
        if prev_vote is None:
            if len(meme.votes) == 1:
                if action == "urgent":
                    message_text = "Криптоселектарх проголосовал срочную публикацию мема!"
                elif action == "approve":
                    message_text = "Криптоселектарх проголосовал ЗА ваш мем!"
                else:
                    message_text = "Криптоселектарх отверг ваш несмешной мем!"
            else:
                if action == "urgent":
                    message_text = "Ещё один криптоселектарх проголосовал срочную публикацию мема!"
                elif action == "approve":
                    message_text = "Ещё один криптоселектарх проголосовал ЗА ваш мем!"
                else:
                    message_text = "Ещё один криптоселектарх отверг ваш несмешной мем!"
            await bot.send_message(meme.user_id, message_text)
        else:
            await bot.send_message(meme.user_id, "Мудрый криптоселектарх изменил своё решение.")

        await callback.answer("Ваш голос учтён.", show_alert=False)

        # Если CRYPTOSELECTARCHY=False, работаем в одноголосном режиме
        if not CRYPTOSELECTARCHY:
            if action in ("approve", "urgent"):
                await scheduler.schedule(meme)
                await bot.send_message(meme.user_id, f"Мем (ID {meme.meme_id}) одобрен и будет опубликован.")
            else:
                await bot.send_message(meme.user_id, "Ваш мем отклонён криптоселектархом.")
            await remove_voting_buttons(meme)
            del pending_memes[meme.meme_id]
            return

        # Многоголосная логика: проверяем, достигнуто ли общее число голосов
        if meme.is_approved():
            if action in ("approve", "urgent"):
                if meme.is_urgent():
                    await publish_meme(meme)
                    await bot.send_message(meme.user_id, "Ваш мем одобрен срочно и опубликован без очереди!")
                else:
                    await scheduler.schedule(meme)
                    await bot.send_message(meme.user_id, "Ваш мем одобрен и будет опубликован.")
            await remove_voting_buttons(meme)
            del pending_memes[meme.meme_id]
            return

        if meme.is_rejected():
            await bot.send_message(meme.user_id, "Мем набрал слишком много голосов ПРОТИВ и отклонён.")
            await remove_voting_buttons(meme)
            del pending_memes[meme.meme_id]
            return

    # Запускаем планировщик
    asyncio.create_task(scheduler.run())
    # Запускаем бота
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
