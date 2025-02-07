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

# Устанавливаем уровень логирования для отладки
logging.basicConfig(level=logging.INFO)

# Загружаем переменные окружения из файла .env
load_dotenv()

# Получаем значения переменных окружения
API_TOKEN = os.getenv("BOT_TOKEN")
EDITOR_IDS_STR = os.getenv("EDITOR_IDS")
PUBLISH_CHAT_ID = os.getenv("PUBLISH_CHAT_ID")
BOT_NAME = os.getenv("BOT_NAME")
POST_FREQUENCY_MINUTES_STR = os.getenv("POST_FREQUENCY_MINUTES")
CRYPTOSELECTARCHY_STR = os.getenv("CRYPTOSELECTARCHY")
VOTES_TO_APPROVE_STR = os.getenv("VOTES_TO_APPROVE")
VOTES_TO_REJECT_STR = os.getenv("VOTES_TO_REJECT")

# Проверка обязательных переменных окружения
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

# Преобразуем полученные строковые значения в нужные типы
PUBLISH_CHAT_ID = int(PUBLISH_CHAT_ID)
POST_FREQUENCY_MINUTES = int(POST_FREQUENCY_MINUTES_STR)
# Если переменная CRYPTOSELECTARCHY равна "true" (без учета регистра) – режим многоголосия включен
CRYPTOSELECTARCHY = CRYPTOSELECTARCHY_STR.lower() == "true"
VOTES_TO_APPROVE = int(VOTES_TO_APPROVE_STR)
VOTES_TO_REJECT = int(VOTES_TO_REJECT_STR)
# Разбиваем строку ID редакторов и преобразуем их в целые числа
EDITOR_IDS = [int(x.strip()) for x in EDITOR_IDS_STR.split(",")]

# Выводим сообщение о режиме работы бота
if CRYPTOSELECTARCHY:
    print("Криптоселектархическая олигархия включена! Власть принадлежит тайному совету мудрецов.")
else:
    print("Единоличный Узурпатор у власти. Все решения принимает один человек.")

# Список строк для формирования префикса анонимного мема (будут случайным образом выбраны)
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

# Создаем экземпляр бота с указанным токеном и настройками (HTML-разметка по умолчанию)
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))

# Словарь для хранения выбора способа публикации пользователями (от имени или анонимно)
user_publish_choice = {}

# Универсальная функция для отправки медиа-сообщений или текстовых сообщений.
# Определяет тип сообщения (фото, видео, гиф и т.д.) и отправляет его.
async def send_media_message(telegram_bot: Bot, chat_id: int, content: Message, caption: str = None, reply_markup=None):
    if not caption:
        caption = content.caption if content.caption else content.text
    caption = caption or ""
    if content.photo:
        return await telegram_bot.send_photo(
            chat_id=chat_id,
            photo=content.photo[-1].file_id,  # выбираем последнее фото (наивысшее качество)
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

# Класс Meme хранит данные о меме, его содержимом и голосах модераторов.
class Meme:
    def __init__(self, meme_id: int, user_id: int, publish_choice: str, content: Message):
        self.meme_id = meme_id  # Уникальный идентификатор мема
        self.user_id = user_id  # ID автора мема
        self.publish_choice = publish_choice  # Выбранный способ публикации: "user" или "potato"
        self.content = content  # Сообщение с контентом мема
        self.votes = {}  # Словарь голосов: ключ – ID модератора, значение – тип голоса ("approve", "urgent", "reject")
        self.mod_messages = []  # Список кортежей (chat_id, message_id) сообщений, отправленных модераторам
        self.finalized = False  # Флаг, указывающий, что итоговое решение уже вынесено (чтобы не дублировать уведомления)

    # Метод для добавления или изменения голоса модератора
    def add_vote(self, crypto_id: int, vote: str) -> str:
        prev_vote = self.votes.get(crypto_id)
        self.votes[crypto_id] = vote
        return prev_vote

    # Метод подсчета голосов по определенному типу. Для "approve" учитываются и обычные, и срочные голоса.
    def count_votes(self, vote_type: str) -> int:
        if vote_type == "approve":
            return sum(1 for v in self.votes.values() if v in ("approve", "urgent"))
        return sum(1 for v in self.votes.values() if v == vote_type)

    # Метод определяет, достигло ли число голосов одобрения порога для публикации
    def is_approved(self) -> bool:
        return self.count_votes("approve") >= VOTES_TO_APPROVE

    # Метод определяет, является ли мем срочным (достаточное количество "urgent" голосов)
    def is_urgent(self) -> bool:
        urgent_count = sum(1 for v in self.votes.values() if v == "urgent")
        urgent_threshold = math.ceil(VOTES_TO_APPROVE * 0.51)
        return urgent_count >= urgent_threshold

    # Метод определяет, набрал ли мем достаточное число голосов против публикации
    def is_rejected(self) -> bool:
        return self.count_votes("reject") >= VOTES_TO_REJECT

    # Метод возвращает сводку голосов в виде строки: (✅ X | ⚡ Y | ❌ Z)
    def get_vote_summary(self) -> str:
        approve_count = sum(1 for v in self.votes.values() if v == "approve")
        urgent_count = sum(1 for v in self.votes.values() if v == "urgent")
        reject_count = sum(1 for v in self.votes.values() if v == "reject")
        return f"(✅ {approve_count} | ⚡ {urgent_count} | ❌ {reject_count})"

    # Метод формирует финальный текст мема для публикации, добавляя префикс (имя автора или анонимное сообщение)
    def get_caption(self) -> str:
        user_text = self.content.caption if self.content.caption else self.content.text
        if self.publish_choice == "user":
            prefix = f"Мем от @{self.content.from_user.username or self.user_id}"
        else:
            # Для анонимной публикации выбирается случайный металл/токсин
            random_metal = random.choice(METALS_AND_TOXINS)
            plain_prefix = f"Мем от Анонимной {random_metal} Картошки"
            # Префикс оборачивается в tg-spoiler для скрытия
            prefix = f"<tg-spoiler>{plain_prefix}</tg-spoiler>"
        return f"{prefix}\n\n{user_text}" if user_text else prefix

# Класс Scheduler отвечает за планирование публикации мема с учетом "окна тишины"
class Scheduler:
    def __init__(self, post_frequency_minutes: int):
        self.post_frequency_minutes = post_frequency_minutes  # Интервал между публикациями
        self.last_published_time = datetime.min.replace(tzinfo=timezone.utc)  # Время последней публикации
        self.scheduled_posts = []  # Очередь запланированных публикаций (список кортежей (scheduled_time, meme))

    @staticmethod
    def get_next_allowed_time(dt: datetime) -> datetime:
        """
        Если переданное время попадает в окно тишины (00:00–07:00 UTC),
        возвращает время 07:00 того же дня, иначе возвращает dt без изменений.
        """
        if dt.hour < 7:
            return dt.replace(hour=7, minute=0, second=0, microsecond=0)
        return dt

    # Метод планирует публикацию мема
    async def schedule(self, meme: Meme):
        now = datetime.now(timezone.utc)
        # Базовое время публикации – максимум между текущим временем и временем последней публикации + интервал
        base_time = max(now, self.last_published_time + timedelta(minutes=self.post_frequency_minutes))
        # Корректируем базовое время с учетом окна тишины
        next_possible_time = self.get_next_allowed_time(base_time)

        # Если время публикации уже наступило (и очередь пуста), публикуем мем сразу
        if next_possible_time <= now and not self.scheduled_posts:
            await publish_meme(meme)
            self.last_published_time = datetime.now(timezone.utc)
            await bot.send_message(meme.user_id, "Ваш мем одобрен и опубликован немедленно!")
        else:
            # Если в очереди уже есть публикации, планируем следующее время от последнего запланированного
            if self.scheduled_posts:
                last_scheduled_time = self.scheduled_posts[-1][0]
                base_time2 = last_scheduled_time + timedelta(minutes=self.post_frequency_minutes)
                scheduled_time = self.get_next_allowed_time(base_time2)
            else:
                scheduled_time = next_possible_time

            # Добавляем мем в очередь публикаций и сортируем по времени публикации
            self.scheduled_posts.append((scheduled_time, meme))
            self.scheduled_posts.sort(key=lambda x: x[0])

            # Вычисляем оставшееся время до публикации для уведомления автора
            time_diff = (scheduled_time - now).total_seconds()
            if time_diff < 0:
                time_diff = 0
            hours = int(time_diff // 3600)
            minutes_left = int((time_diff % 3600) // 60)
            time_left_str = f"{hours} ч. {minutes_left} мин." if hours > 0 else f"{minutes_left} мин."

            await bot.send_message(
                meme.user_id,
                f"Ваш мем одобрен и теперь ждёт очереди на публикацию.\n\n"
                f"Ориентировочное время публикации: {scheduled_time.strftime('%H:%M')} по UTC\n"
                f"(через {time_left_str})."
            )

    # Метод run постоянно проверяет очередь запланированных публикаций и публикует мемы, когда наступает время
    async def run(self):
        while True:
            now = datetime.now(timezone.utc)
            if self.scheduled_posts:
                self.scheduled_posts.sort(key=lambda x: x[0])
                next_time, meme = self.scheduled_posts[0]
                wait_seconds = (next_time - now).total_seconds()
                if wait_seconds > 0:
                    await asyncio.sleep(min(wait_seconds, 10))
                else:
                    self.scheduled_posts.pop(0)
                    await publish_meme(meme)
                    self.last_published_time = datetime.now(timezone.utc)
            else:
                await asyncio.sleep(10)

# Функция обновляет сообщения модераторов: вместо кнопок появляется итоговая резолюция
# с указанием сводки голосов, например: "✅ Одобрен (✅ 4 | ⚡ 1 | ❌ 2)"
async def update_mod_messages_with_resolution(meme: Meme, resolution: str):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=resolution, callback_data="noop")]
    ])
    for chat_id, message_id in meme.mod_messages:
        try:
            await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=keyboard)
        except Exception as e:
            logging.error(f"Ошибка при обновлении сообщения для криптоселектарха {chat_id}: {e}")

# Функция публикует мем в конечный чат
async def publish_meme(meme: Meme):
    try:
        await send_media_message(
            telegram_bot=bot,
            chat_id=PUBLISH_CHAT_ID,
            content=meme.content,
            caption=meme.get_caption()
        )
    except Exception as e:
        logging.error(f"Ошибка при публикации: {e}")

# Глобальные структуры для хранения мема и планировщика публикаций
pending_memes = {}  # Словарь, где ключ – meme_id, значение – объект Meme
meme_counter = 0
scheduler = Scheduler(POST_FREQUENCY_MINUTES)

# Основная функция запуска бота и диспетчера команд
async def main():
    dp = Dispatcher()

    # Команда /start отправляет пользователю выбор способа публикации мема
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
                "Решения теперь принимаются коллективно тайно отобранными правителями.\n\n"
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

    # Обработчик выбора способа публикации (от имени или анонимно)
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

    # Обработчик входящих сообщений с мемом (текст, фото, видео и т.д.)
    @dp.message(F.content_type.in_(["text", "photo", "video", "animation", "voice", "video_note"]))
    async def handle_meme_suggestion(message: Message):
        user_id = message.from_user.id
        # Если пользователь ещё не выбрал способ публикации, просим его сначала отправить /start
        if user_id not in user_publish_choice:
            await message.answer("Сначала выберите способ публикации с помощью команды /start.")
            return

        global meme_counter
        meme_counter += 1
        # Создаем объект Meme и сохраняем его в словаре pending_memes
        meme = Meme(meme_counter, user_id, user_publish_choice[user_id], message)
        pending_memes[meme.meme_id] = meme

        # Формируем клавиатуру для модераторов с кнопками голосования
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅Одобр.", callback_data=f"approve_{meme.meme_id}"),
                InlineKeyboardButton(text="⚡Срочно⚡", callback_data=f"urgent_{meme.meme_id}"),
                InlineKeyboardButton(text="❌Отклонить", callback_data=f"reject_{meme.meme_id}")
            ]
        ])

        # Формируем информационный текст о меме для модераторов
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

        # Отправляем сообщение модераторам (редакторам) и сохраняем id их сообщений для последующего обновления
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

    # Обработчик нажатий кнопок модераторов ("approve", "urgent", "reject")
    @dp.callback_query(F.data.startswith(("approve_", "urgent_", "reject_")))
    async def crypto_callback(callback: CallbackQuery):
        data = callback.data
        action, meme_id_str = data.split("_", 1)
        meme_id = int(meme_id_str)
        # Если мем уже не найден (обработан), уведомляем модератора
        if meme_id not in pending_memes:
            await callback.answer("Заявка не найдена или уже обработана.")
            return

        meme = pending_memes[meme_id]
        crypto_id = callback.from_user.id

        # Добавляем голос модератора. Если он ранее не голосовал, prev_vote будет None
        prev_vote = meme.add_vote(crypto_id, action)

        # Если голос новый, отправляем уведомление автору о голосовании
        if prev_vote is None:
            if len(meme.votes) == 1:
                # Первый голос
                if action == "urgent":
                    message_text = "Криптоселектарх проголосовал за срочную публикацию мема!"
                elif action == "approve":
                    message_text = "Криптоселектарх проголосовал ЗА ваш мем!"
                else:
                    message_text = "Криптоселектарх отверг ваш несмешной мем!"
            else:
                # Последующие голоса
                if action == "urgent":
                    message_text = "Ещё один криптоселектарх проголосовал за срочную публикацию мема!"
                elif action == "approve":
                    message_text = "Ещё один криптоселектарх проголосовал ЗА ваш мем!"
                else:
                    message_text = "Ещё один криптоселектарх отверг ваш несмешной мем!"
            await bot.send_message(meme.user_id, message_text)
        else:
            # Если модератор меняет своё решение, уведомляем автора с указанием нового мнения
            if action == "urgent":
                new_vote_text = "срочную публикацию мема!"
            elif action == "approve":
                new_vote_text = "ЗА ваш мем!"
            else:
                new_vote_text = "отказ от публикации мема!"
            await bot.send_message(meme.user_id, f"Мудрый криптоселектарх изменил своё решение. Новое мнение: {new_vote_text}")

        await callback.answer("Ваш голос учтён.", show_alert=False)

        # Режим единоличного решения: публикация происходит сразу после первого голосования
        if not CRYPTOSELECTARCHY:
            if action in ("approve", "urgent"):
                # Если голос "urgent" – мем считается срочным
                resolution = "⚡ Одобрен срочно" if action == "urgent" else "✅ Одобрен"
                await scheduler.schedule(meme)
                await bot.send_message(meme.user_id, f"Мем (ID {meme.meme_id}) одобрен и будет опубликован.")
            else:
                resolution = "❌ Отклонён"
                await bot.send_message(meme.user_id, "Ваш мем отклонён криптоселектархом.")
            # Формируем итоговую строку с резолюцией и сводкой голосов
            resolution_with_summary = f"{resolution} {meme.get_vote_summary()}"
            await update_mod_messages_with_resolution(meme, resolution_with_summary)
            del pending_memes[meme.meme_id]
            return

        # Многоголосная система: завершаем голосование только один раз,
        # проверяя, достиг ли мем порога одобрения
        if meme.is_approved() and not meme.finalized:
            # Если мем считается срочным, он публикуется сразу (даже если окно тишины)
            if meme.is_urgent():
                resolution = "⚡ Одобрен срочно"
                await publish_meme(meme)
                await bot.send_message(meme.user_id, "Ваш мем одобрен срочно и опубликован без очереди!")
            else:
                resolution = "✅ Одобрен"
                await scheduler.schedule(meme)
                await bot.send_message(meme.user_id, "Ваш мем одобрен и будет опубликован.")
            meme.finalized = True  # Помечаем мем как обработанный
            resolution_with_summary = f"{resolution} {meme.get_vote_summary()}"
            await update_mod_messages_with_resolution(meme, resolution_with_summary)
            del pending_memes[meme.meme_id]
            return

        # Если мем набрал достаточное число голосов против публикации, отклоняем мем
        if meme.is_rejected() and not meme.finalized:
            resolution = "❌ Отклонён"
            await bot.send_message(meme.user_id, "Мем набрал слишком много голосов ПРОТИВ и отклонён.")
            meme.finalized = True
            resolution_with_summary = f"{resolution} {meme.get_vote_summary()}"
            await update_mod_messages_with_resolution(meme, resolution_with_summary)
            del pending_memes[meme.meme_id]
            return

    # Обработчик для неактивной кнопки (резолюция) – кнопка больше не реагирует на нажатия
    @dp.callback_query(lambda c: c.data == "noop")
    async def noop_callback(callback: CallbackQuery):
        await callback.answer("Голосование завершено, эта кнопка не активна.", show_alert=True)

    # Запускаем планировщик публикаций в отдельной задаче
    asyncio.create_task(scheduler.run())
    # Запускаем бота (поллинг)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
