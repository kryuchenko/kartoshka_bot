# karoshka_bot.py
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

# Преобразуем EDITOR_IDS_STR в список int
EDITOR_IDS = [int(x.strip()) for x in EDITOR_IDS_STR.split(",")]

# Приводим PUBLISH_CHAT_ID к int
PUBLISH_CHAT_ID = int(PUBLISH_CHAT_ID)

# ----------------------------
# ГЛОБАЛЬНЫЕ СТРУКТУРЫ ДАННЫХ
# ----------------------------
user_publish_choice = {}  # user_id -> "user" или "potato"
pending_memes = {}  # meme_id -> {...}

# Глобальный счётчик для ID мемов
meme_counter = 0


async def main():
    bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()

    # /start — запрос, как публиковать
    @dp.message(Command("start"))
    async def cmd_start(message: Message):\
        kb = [
        [
            types.KeyboardButton(text="user"),
            types.KeyboardButton(text="potato")
        ],
    ]
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True,
        input_field_placeholder="Выберите способ публикации мема"
    )
        await message.answer("Привет! Я бот «{BOT_NAME}».\n\nКак вы хотите опубликовать мем?\n- user   => от своего имени\n- potato => от имени картошки", reply_markup=keyboard

    # Если пользователь напишет "user"
    @dp.message(F.text == "user")
    async def set_user_choice(message: Message):
        user_publish_choice[message.from_user.id] = "user"
        await message.answer("Буду публиковать от вашего имени. Пришлите мем (текст/фото).")

    # Если пользователь напишет "potato"
    @dp.message(F.text == "potato")
    async def set_potato_choice(message: Message):
        user_publish_choice[message.from_user.id] = "potato"
        await message.answer("Буду публиковать от имени картошки. Пришлите мем (текст/фото).")

    # Принимаем фото или текст (для простоты - всё в одном хендлере)
    @dp.message(F.content_type.in_({"text", "photo"}))
    async def handle_meme_suggestion(message: Message):
        user_id = message.from_user.id

        # Если не выбрали "user" или "potato"
        if user_id not in user_publish_choice:
            await message.answer("Сначала введите 'user' или 'potato'.")
            return

        global meme_counter
        meme_counter += 1
        meme_id = meme_counter

        # Сохраняем данные во временную структуру
        pending_memes[meme_id] = {
            "user_id": user_id,
            "publish_choice": user_publish_choice[user_id],
            "content": message
        }

        # Кнопки "Одобрить"/"Отклонить" для редактора
        approve_button = InlineKeyboardButton(text="Одобрить", callback_data=f"approve_{meme_id}")
        reject_button = InlineKeyboardButton(text="Отклонить", callback_data=f"reject_{meme_id}")
        keyboard_for_editor = InlineKeyboardMarkup(inline_keyboard=[[approve_button, reject_button]])

        # Отправляем редактору(ам) на модерацию
        for editor_id in EDITOR_IDS:
            if message.photo:
                largest_photo = message.photo[-1].file_id
                await bot.send_photo(
                    chat_id=editor_id,
                    photo=largest_photo,
                    caption=(
                        f"Мем ID: {meme_id}\n"
                        f"От @{message.from_user.username or message.from_user.id}\n"
                        f"Публикация как: {user_publish_choice[user_id]}"
                    ),
                    reply_markup=keyboard_for_editor
                )
            else:
                # Текст
                await bot.send_message(
                    chat_id=editor_id,
                    text=(
                        f"Мем ID: {meme_id}\n\n"
                        f"{message.text}\n\n"
                        f"От @{message.from_user.username or message.from_user.id}\n"
                        f"Публикация как: {user_publish_choice[user_id]}"
                    ),
                    reply_markup=keyboard_for_editor
                )

        await message.answer("Ваш мем отправлен на модерацию.")

    # Обработка нажатия кнопок "Одобрить"/"Отклонить"
    @dp.callback_query(F.data.startswith(("approve_", "reject_")))
    async def editor_callback(callback: CallbackQuery):
        data = callback.data  # напр. "approve_5"
        action, meme_id_str = data.split("_")
        meme_id = int(meme_id_str)

        if meme_id not in pending_memes:
            await callback.answer("Заявка не найдена или уже обработана.")
            return

        meme_info = pending_memes[meme_id]
        user_id = meme_info["user_id"]
        choice = meme_info["publish_choice"]
        original_message = meme_info["content"]

        if action == "approve":
            try:
                if original_message.photo:
                    largest_photo = original_message.photo[-1].file_id
                    # Если user => упоминаем автора, иначе => анонимная картошка
                    cap = (
                        f"Мем от @{original_message.from_user.username or user_id}"
                        if choice == "user"
                        else "Мем от Анонимной Аллюминиевой Картошки"
                    )
                    await bot.send_photo(PUBLISH_CHAT_ID, photo=largest_photo, caption=cap)
                else:
                    # Текстовый мем
                    txt = (
                        f"Мем от @{original_message.from_user.username or user_id}:\n\n{original_message.text}"
                        if choice == "user"
                        else f"Мем от Анонимной Аллюминиевой Картошки:\n\n{original_message.text}"
                    )
                    await bot.send_message(PUBLISH_CHAT_ID, txt)

                # Уведомляем автора
                await bot.send_message(user_id, "Ваш мем одобрен и опубликован!")
                # Уведомляем редактора
                await callback.message.answer(f"Мем (ID {meme_id}) одобрен.")
            except Exception as e:
                logging.error(f"Ошибка при публикации: {e}")
                await callback.message.answer(f"Не удалось опубликовать мем {meme_id}. Ошибка: {e}")
        else:
            # Отклоняем
            await bot.send_message(user_id, "Ваш мем отклонён редактором.")
            await callback.message.answer(f"Мем (ID {meme_id}) отклонён.")

        # Удаляем из памяти
        del pending_memes[meme_id]
        await callback.answer()

    # Запускаем бота (polling)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
