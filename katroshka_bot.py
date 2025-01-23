import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from dotenv import load_dotenv
from aiogram.client.bot import DefaultBotProperties

logging.basicConfig(level=logging.INFO)

# Загружаем переменные из файла .env
load_dotenv()

# Читаем конфиг из окружения (.env)
API_TOKEN = os.getenv("BOT_TOKEN")
EDITOR_IDS_STR = os.getenv("EDITOR_IDS")  # может быть несколько ID через запятую
PUBLISH_CHAT_ID = os.getenv("PUBLISH_CHAT_ID")
BOT_NAME = os.getenv("BOT_NAME")

# Проверяем наличие всех обязательных переменных
required_env_vars = {
    "BOT_TOKEN": API_TOKEN,
    "EDITOR_IDS": EDITOR_IDS_STR,
    "PUBLISH_CHAT_ID": PUBLISH_CHAT_ID,
    "BOT_NAME": BOT_NAME,
}
missing_vars = [k for k, v in required_env_vars.items() if not v]
if missing_vars:
    raise ValueError(f"Отсутствуют обязательные переменные окружения: {missing_vars}")

# Преобразуем EDITOR_IDS_STR в список int
EDITOR_IDS = [int(x.strip()) for x in EDITOR_IDS_STR.split(",")]

# Приводим PUBLISH_CHAT_ID к int
PUBLISH_CHAT_ID = int(PUBLISH_CHAT_ID)

# ----------------------------
# ГЛОБАЛЬНЫЕ СТРУКТУРЫ ДАННЫХ
# ----------------------------
user_publish_choice = {}  # user_id -> "user" или "potato"
pending_memes = {}        # meme_id -> {...}

# Глобальный счётчик для ID мемов
meme_counter = 0


async def main():
    bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()

    # /start — запрос, как публиковать
    @dp.message(Command("start"))
    async def cmd_start(message: Message):
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👤 Публиковать от своего имени",
                        callback_data="choice_user"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🥔 Публиковать анонимно (от \"картошки\")",
                        callback_data="choice_potato"
                    )
                ]
            ]
        )
        await message.answer(
            f"Привет! Я бот «{BOT_NAME}».\nКак вы хотите опубликовать мем?",
            reply_markup=keyboard
        )

    # Обработка выбора кнопок "user" или "potato"
    @dp.callback_query(F.data.in_({"choice_user", "choice_potato"}))
    async def handle_choice(callback: CallbackQuery):
        user_id = callback.from_user.id

        if callback.data == "choice_user":
            user_publish_choice[user_id] = "user"
            await callback.message.answer(
                "Буду публиковать от вашего имени. Пришлите мем (текст/фото/видео)."
            )
        else:
            user_publish_choice[user_id] = "potato"
            await callback.message.answer(
                "Буду публиковать анонимно (от имени «картошки»). Пришлите мем (текст/фото/видео)."
            )

        await callback.answer()

    # Принимаем фото, видео или текст (в одном хендлере)
    @dp.message(F.content_type.in_({"text", "photo", "video"}))
    async def handle_meme_suggestion(message: Message):
        user_id = message.from_user.id

        # Если не выбрали "user" или "potato" — просим сначала сделать выбор
        if user_id not in user_publish_choice:
            await message.answer(
                "Сначала выберите способ публикации с помощью команды /start."
            )
            return

        global meme_counter
        meme_counter += 1
        meme_id = meme_counter

        # Сохраним оригинал сообщения, чтобы при модерации знать что было
        pending_memes[meme_id] = {
            "user_id": user_id,
            "publish_choice": user_publish_choice[user_id],
            "content": message
        }

        # Кнопки "Одобрить"/"Отклонить" для редактора
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

        # Определяем, как отобразить имя отправителя
        if user_publish_choice[user_id] == "user":
            from_text = f"От @{message.from_user.username or message.from_user.id}"
        else:
            from_text = "От Анонимного пользователя"

        # Формируем текст для редактора
        # Если пользователь прислал подпись (caption) к фото/видео — берём её,
        # иначе берём message.text для текстовых сообщений
        user_text = message.caption if message.caption else message.text

        # Рассылаем всем редакторам для одобрения
        for editor_id in EDITOR_IDS:
            if message.photo:
                # Фото
                largest_photo_id = message.photo[-1].file_id
                await bot.send_photo(
                    chat_id=editor_id,
                    photo=largest_photo_id,
                    caption=(
                        f"Мем ID: {meme_id}\n\n"
                        f"{user_text}\n\n"
                        f"{from_text}\n"
                        f"Публикация как: {user_publish_choice[user_id]}"
                    ),
                    reply_markup=keyboard_for_editor
                )
            elif message.video:
                # Видео
                video_id = message.video.file_id
                await bot.send_video(
                    chat_id=editor_id,
                    video=video_id,
                    caption=(
                        f"Мем ID: {meme_id}\n\n"
                        f"{user_text}\n\n"
                        f"{from_text}\n"
                        f"Публикация как: {user_publish_choice[user_id]}"
                    ),
                    reply_markup=keyboard_for_editor
                )
            else:
                # Текстовое сообщение
                await bot.send_message(
                    chat_id=editor_id,
                    text=(
                        f"Мем ID: {meme_id}\n\n"
                        f"{user_text}\n\n"
                        f"{from_text}\n"
                        f"Публикация как: {user_publish_choice[user_id]}"
                    ),
                    reply_markup=keyboard_for_editor
                )

        await message.answer("Ваш мем отправлен на модерацию.")

    # Обработка кнопок "Одобрить"/"Отклонить"
    @dp.callback_query(F.data.startswith(("approve_", "reject_")))
    async def editor_callback(callback: CallbackQuery):
        data = callback.data  # например, "approve_5"
        action, meme_id_str = data.split("_")
        meme_id = int(meme_id_str)

        if meme_id not in pending_memes:
            await callback.answer("Заявка не найдена или уже обработана.")
            return

        meme_info = pending_memes[meme_id]
        user_id = meme_info["user_id"]
        choice = meme_info["publish_choice"]
        original_message = meme_info["content"]

        # То, что написал пользователь (caption или text)
        user_text = original_message.caption if original_message.caption else original_message.text

        if action == "approve":
            try:
                # Формируем подпись для канала
                # При публикации от имени пользователя или анонимно
                if choice == "user":
                    # Укажем @username, если есть, иначе user_id
                    prefix = f"Мем от @{original_message.from_user.username or user_id}"
                else:
                    prefix = "Мем от Анонимной Аллюминиевой Картошки"

                # Публикация
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
                else:
                    # Текст
                    text_for_channel = f"{prefix}:\n\n{user_text}"
                    await bot.send_message(
                        chat_id=PUBLISH_CHAT_ID,
                        text=text_for_channel
                    )

                # Уведомляем автора
                await bot.send_message(user_id, "Ваш мем одобрен и опубликован!")
                await callback.message.answer(f"Мем (ID {meme_id}) одобрен и опубликован.")
            except Exception as e:
                logging.error(f"Ошибка при публикации: {e}")
                await callback.message.answer(
                    f"Не удалось опубликовать мем (ID {meme_id}). Ошибка: {e}"
                )
        else:
            # Отклонение
            await bot.send_message(user_id, "Ваш мем отклонён редактором.")
            await callback.message.answer(f"Мем (ID {meme_id}) отклонён.")

        # Удаляем из списка на модерацию
        del pending_memes[meme_id]
        await callback.answer()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
