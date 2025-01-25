import asyncio
import logging
import os
import datetime
import random

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from dotenv import load_dotenv
from aiogram.client.bot import DefaultBotProperties

logging.basicConfig(level=logging.INFO)

# Загружаем переменные из файла .env
load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")
EDITOR_IDS_STR = os.getenv("EDITOR_IDS")  # может быть несколько ID через запятую
PUBLISH_CHAT_ID = os.getenv("PUBLISH_CHAT_ID")
BOT_NAME = os.getenv("BOT_NAME")
POST_FREQUENCY_MINUTES_STR = os.getenv("POST_FREQUENCY_MINUTES")  # Частота постов в минутах (строка)
CRYPTOSELECTARCHY_STR = os.getenv("CRYPTOSELECTARCHY")  # Строка "true" или "false"
VOTES_TO_APPROVE_STR = os.getenv("VOTES_TO_APPROVE")
VOTES_TO_REJECT_STR = os.getenv("VOTES_TO_REJECT")

# Список металлов и токсинов остаётся в коде
METALS_AND_TOXINS = [
    "Алюминиевой", "Железной", "Медной", "Свинцовой", "Цинковой", "Титановой", "Никелевой",
    "Оксид-железной", "Оксид-цинковой", "Оксид-титановой", "Урановой", "Плутониевой", "Ториевой",
    "Радиевой", "Полониевой", "Актиниевой", "Протактиниевой", "Америциевой", "Кюриевой",
    "Нептуниевой", "Франциевой", "Лоуренсиевой", "Рутениевой", "Цезиевой", "Бериллиевой",
    "Уран-235", "Диоксид-ториевой", "Карбонат-радиевой", "Гексафторид-урановой",
    "Нитрат-ториевой", "Оксид-плутониевой", "Дейтериевой", "Тритиевой", "Цианистой",
    "Рициновой", "Сариновой", "Зомановой", "Ви-Иксной (VX)", "Ботулотоксиновой",
    "Стрихнинной", "Фосгеновой", "Диоксиновой", "Тетродоксиновой", "Полониевой-210",
    "Меркуриевой (ртутной)", "Аманитиновой (грибной)", "Арсеновой", "Талиевой",
    "Метанольной", "Этиленгликолевой", "Трихлорэтиленовой", "Хлориновой",
    "Монооксид-углеродной (угарной)", "Гексафторовой", "Фторводородной",
    "Бромацетоновой", "Хлорацетоновой", "Карбофосовой", "Хлороформовой", "Барбитуровой",
    "Калий-цианистой", "Метилртутной"
]

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

# Преобразование переменных в нужные типы
EDITOR_IDS = [int(x.strip()) for x in EDITOR_IDS_STR.split(",")]
PUBLISH_CHAT_ID = int(PUBLISH_CHAT_ID)
POST_FREQUENCY_MINUTES = int(POST_FREQUENCY_MINUTES_STR)
VOTES_TO_APPROVE = int(VOTES_TO_APPROVE_STR)
VOTES_TO_REJECT = int(VOTES_TO_REJECT_STR)
CRYPTOSELECTARCHY = (CRYPTOSELECTARCHY_STR.lower() == "true")

if CRYPTOSELECTARCHY:
    print("Криптоселектархическая олигархия включена! Власть принадлежит тайному совету мудрецов.")
else:
    print("Единоличный Узурпатор у власти. Все решения принимает один человек.")

# Инициализируем бота на уровне модуля
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))

user_publish_choice = {}  # user_id -> "user" или "potato"

# Для каждого meme_id хранится dict с данными о меме и голосами криптоселектархов
pending_memes = {}
meme_counter = 0

# Переменные для управления частотой публикации
last_published_time = datetime.datetime.min
scheduled_posts = []

async def main():
    global last_published_time
    global bot  # Теперь bot уже определён на уровне модуля
    dp = Dispatcher()

    @dp.message(Command("start"))
    async def cmd_start(message: Message):
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👤 От своего имени (ваше имя будет указано).",
                        callback_data="choice_user"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🥔 Анонимно (от имени «Картошки»).",
                        callback_data="choice_potato"
                    )
                ]
            ]
        )

        if CRYPTOSELECTARCHY:
            intro_text = (
                f"Привет! Я бот {BOT_NAME}.\n\n"
                "Ура! Свершилось! Гадкий Узурпатор канул в небытие, и теперь наступила эпоха Криптоселектархической олигархии!\n"
                "Решения теперь принимаются коллективно тайно отобранными правителями. Настало время справедливости!\n\n"
                "Как вы хотите опубликовать мем?"
            )
        else:
            intro_text = (
                f"Привет! Я {BOT_NAME}.\n\n"
                "Сейчас ещё не наступила Криптоселектархическая олигархия.\n"
                "Во власти находится Единоличный Узурпатор, но не переживайте! Когда-нибудь он отойдёт от власти и передаст её группе мудрых Криптоселектархов.\n\n"
                "Как вы хотите опубликовать мем?"
            )

        await message.answer(intro_text, reply_markup=keyboard)

    @dp.callback_query(F.data.in_({"choice_user", "choice_potato"}))
    async def handle_choice(callback: CallbackQuery):
        user_id = callback.from_user.id

        if callback.data == "choice_user":
            user_publish_choice[user_id] = "user"
            await callback.message.answer(
                "Буду публиковать от вашего имени. Пришлите мем (текст/фото/видео/gif)."
            )
        else:
            user_publish_choice[user_id] = "potato"
            await callback.message.answer(
                "Буду публиковать анонимно (от имени «Картошки»). Пришлите мем (текст/фото/видео/gif)."
            )
        await callback.answer()

    # Добавляем "animation" для gif
    @dp.message(F.content_type.in_({"text", "photo", "video", "animation"}))
    async def handle_meme_suggestion(message: Message):
        user_id = message.from_user.id

        # Проверяем, выбрал ли пользователь способ публикации
        if user_id not in user_publish_choice:
            await message.answer(
                "Сначала выберите способ публикации с помощью команды /start."
            )
            return

        global meme_counter
        meme_counter += 1
        meme_id = meme_counter

        # Сохраняем информацию о меме
        pending_memes[meme_id] = {
            "user_id": user_id,
            "publish_choice": user_publish_choice[user_id],
            "content": message,
            "votes": {}  # editor_id -> "approve" или "reject"
        }

        # Кнопки голосования
        approve_button = InlineKeyboardButton(
            text="✅ Одобрить",
            callback_data=f"approve_{meme_id}"
        )
        reject_button = InlineKeyboardButton(
            text="❌ Отклонить",
            callback_data=f"reject_{meme_id}"
        )
        keyboard_for_editor = InlineKeyboardMarkup(
            inline_keyboard=[[approve_button, reject_button]]
        )

        # "От кого" для криптоселектархов
        if user_publish_choice[user_id] == "user":
            from_text = f"От @{message.from_user.username or message.from_user.id}"
        else:
            from_text = "От Анонимного пользователя"

        # Текст мема (caption или text)
        user_text = message.caption if message.caption else message.text
        meme_info_text = (
            f"Мем ID: {meme_id}\n\n"
            f"{user_text}\n\n"
            f"{from_text}\n"
            f"Публикация как: {user_publish_choice[user_id]}"
        )

        # Рассылаем сообщение всем «криптоселектархам» (EDITOR_IDS)
        for editor_id in EDITOR_IDS:
            try:
                if message.photo:
                    largest_photo_id = message.photo[-1].file_id
                    await bot.send_photo(
                        chat_id=editor_id,
                        photo=largest_photo_id,
                        caption=meme_info_text,
                        reply_markup=keyboard_for_editor
                    )
                elif message.video:
                    video_id = message.video.file_id
                    await bot.send_video(
                        chat_id=editor_id,
                        video=video_id,
                        caption=meme_info_text,
                        reply_markup=keyboard_for_editor
                    )
                elif message.animation:
                    animation_id = message.animation.file_id
                    await bot.send_animation(
                        chat_id=editor_id,
                        animation=animation_id,
                        caption=meme_info_text,
                        reply_markup=keyboard_for_editor
                    )
                else:
                    # Текстовый мем
                    await bot.send_message(
                        chat_id=editor_id,
                        text=meme_info_text,
                        reply_markup=keyboard_for_editor
                    )
            except Exception as e:
                logging.error(f"Не удалось отправить сообщение криптоселектарху {editor_id}: {e}")

        await message.answer("Ваш мем отправлен на модерацию.")

    @dp.callback_query(F.data.startswith(("approve_", "reject_")))
    async def editor_callback(callback: CallbackQuery):
        data = callback.data
        action, meme_id_str = data.split("_")
        meme_id = int(meme_id_str)

        # Проверяем, есть ли такой мем ещё в ожидании
        if meme_id not in pending_memes:
            await callback.answer("Заявка не найдена или уже обработана.")
            return

        meme_info = pending_memes[meme_id]
        user_id = meme_info["user_id"]
        votes_dict = meme_info["votes"]

        editor_id = callback.from_user.id

        # Получаем предыдущий голос криптоселектарха (если был)
        prev_vote = votes_dict.get(editor_id)

        # Проверяем, изменился ли голос
        if prev_vote == action:
            # Голос не изменился, не нужно повторно уведомлять пользователя
            await callback.answer("Ваш голос уже был учтён.", show_alert=False)
            return
        else:
            # Обновляем голос криптоселектарха
            votes_dict[editor_id] = action  # "approve" или "reject"

        # --- Если криптоселектархическая олигархия (Cryptoselectarchy) выключена ---
        if not CRYPTOSELECTARCHY:
            # Обычный режим: один голос всё решает
            if action == "approve":
                try:
                    await schedule_or_publish_meme(meme_info)
                    await callback.message.answer(f"Мем (ID {meme_id}) одобрен и будет опубликован.")
                    # Уведомление пользователю будет отправлено внутри schedule_or_publish_meme
                except Exception as e:
                    logging.error(f"Ошибка при публикации: {e}")
                    await callback.message.answer(
                        f"Не удалось обработать мем (ID {meme_id}). Ошибка: {e}"
                    )
            else:
                # Отклонение
                await bot.send_message(user_id, "Ваш мем отклонён редактором.")
                await callback.message.answer(f"Мем (ID {meme_id}) отклонён.")
            # Убираем из «ожидания»
            del pending_memes[meme_id]
            await callback.answer()
            return

        # --- Ниже логика при включённой криптоселектархической олигархии ---
        # Подсчитываем голоса
        approves = sum(1 for v in votes_dict.values() if v == "approve")
        rejects = sum(1 for v in votes_dict.values() if v == "reject")
        total_votes = len(votes_dict)

        # Уведомляем криптоселектарха, что его голос учтён
        await callback.answer("Ваш голос учтён.", show_alert=False)

        # Отправляем автору уведомление о голосе
        if prev_vote is None:
            # Новый голос от этого криптоселектарха
            if total_votes == 1:
                # Это первый голос по этому мему
                if action == "approve":
                    await bot.send_message(
                        user_id,
                        "Криптоселектарх проголосовал ЗА ваш мем!"
                    )
                else:
                    await bot.send_message(
                        user_id,
                        "Криптоселектарх отверг ваш несмешной мем!"
                    )
            else:
                # Не первый голос, но этот криптоселектарх голосует впервые
                if action == "approve":
                    await bot.send_message(
                        user_id,
                        "Ещё один Криптоселектарх проголосовал ЗА ваш мем!"
                    )
                else:
                    await bot.send_message(
                        user_id,
                        "Ещё один Криптоселектарх отверг ваш несмешной мем!"
                    )
        else:
            # Криптоселектарх изменил своё решение
            if action == "approve":
                await bot.send_message(
                    user_id,
                    "Мудрый Криптоселектарх передумал и теперь ГОЛОСУЕТ ЗА ваш мем."
                )
            else:
                await bot.send_message(
                    user_id,
                    "Мудрый Криптоселектарх передумал и теперь ГОЛОСУЕТ ПРОТИВ вашего мема."
                )

        # Проверяем, достигнут ли пороги голосования
        if approves >= VOTES_TO_APPROVE:
            try:
                await schedule_or_publish_meme(meme_info)
                # Уведомление пользователю будет отправлено внутри schedule_or_publish_meme
                del pending_memes[meme_id]

                # Отключаем кнопки в сообщении, т.к. решение принято
                await callback.message.edit_reply_markup(reply_markup=None)

            except Exception as e:
                logging.error(f"Ошибка при публикации: {e}")
                await callback.message.answer(
                    f"Не удалось обработать мем (ID {meme_id}). Ошибка: {e}"
                )
            return

        if rejects >= VOTES_TO_REJECT:
            await bot.send_message(user_id, "Мем набрал слишком много голосов ПРОТИВ и отклонён.")
            del pending_memes[meme_id]

            # Отключаем кнопки в сообщении
            await callback.message.edit_reply_markup(reply_markup=None)
            return

        # Если голосов ещё недостаточно, ждём дальнейших.

    async def schedule_or_publish_meme(meme_info):
        global last_published_time, scheduled_posts
        user_id = meme_info["user_id"]
        now = datetime.datetime.now()
        next_possible_time = last_published_time + datetime.timedelta(minutes=POST_FREQUENCY_MINUTES)

        # Определяем время публикации
        if now >= next_possible_time and not scheduled_posts:
            # Публикуем немедленно
            await publish_meme(meme_info)
            last_published_time = datetime.datetime.now()
            # Уведомляем пользователя
            await bot.send_message(user_id, "Ваш мем одобрен и опубликован!")
        else:
            # Планируем публикацию
            if scheduled_posts:
                # Запланировать после последнего запланированного мема
                last_scheduled_time = scheduled_posts[-1][0]
                scheduled_time = last_scheduled_time + datetime.timedelta(minutes=POST_FREQUENCY_MINUTES)
            else:
                scheduled_time = next_possible_time

            scheduled_posts.append((scheduled_time, meme_info))
            await bot.send_message(user_id, f"Ваш мем одобрен и теперь ждёт очереди на публикацию. Ориентировочное время публикации: {scheduled_time.strftime('%H:%M')} по UTC")
            # Сортируем список запланированных постов по времени
            scheduled_posts.sort(key=lambda x: x[0])

    async def publish_meme(meme_info):
        user_id = meme_info["user_id"]
        choice = meme_info["publish_choice"]
        original_message = meme_info["content"]

        # Текст мема
        user_text = original_message.caption if original_message.caption else original_message.text

        # Определяем «префикс» для поста
        if choice == "user":
            prefix = f"Мем от @{original_message.from_user.username or user_id}"
        else:
            random_metal = random.choice(METALS_AND_TOXINS)
            prefix = f"Мем от Анонимной {random_metal} Картошки"

        try:
            if original_message.photo:
                photo_id = original_message.photo[-1].file_id
                await bot.send_photo(
                    chat_id=PUBLISH_CHAT_ID,
                    photo=photo_id,
                    caption=(f"{prefix}\n\n{user_text}" if user_text else prefix)
                )
            elif original_message.video:
                video_id = original_message.video.file_id
                await bot.send_video(
                    chat_id=PUBLISH_CHAT_ID,
                    video=video_id,
                    caption=(f"{prefix}\n\n{user_text}" if user_text else prefix)
                )
            elif original_message.animation:
                animation_id = original_message.animation.file_id
                await bot.send_animation(
                    chat_id=PUBLISH_CHAT_ID,
                    animation=animation_id,
                    caption=(f"{prefix}\n\n{user_text}" if user_text else prefix)
                )
            else:
                # Текст
                text_for_channel = f"{prefix}\n\n{user_text}"
                await bot.send_message(
                    chat_id=PUBLISH_CHAT_ID,
                    text=text_for_channel
                )
        except Exception as e:
            logging.error(f"Ошибка при публикации: {e}")

    async def scheduled_publisher():
        global scheduled_posts, last_published_time
        while True:
            now = datetime.datetime.now()
            if scheduled_posts:
                scheduled_posts.sort(key=lambda x: x[0])  # сортируем по времени
                next_time, meme_info = scheduled_posts[0]
                wait_seconds = (next_time - now).total_seconds()
                if wait_seconds > 0:
                    await asyncio.sleep(min(wait_seconds, 10))
                else:
                    # Время публикации
                    scheduled_posts.pop(0)
                    await publish_meme(meme_info)
                    last_published_time = datetime.datetime.now()
            else:
                # Нет запланированных постов, ждем немного
                await asyncio.sleep(10)

    # Запускаем задачу для управления расписанием публикаций
    asyncio.create_task(scheduled_publisher())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
