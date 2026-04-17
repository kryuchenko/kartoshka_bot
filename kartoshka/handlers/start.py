from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from kartoshka import config
from kartoshka.config import BOT_NAME
from kartoshka.state import AppState


def register(dp: Dispatcher, state: AppState) -> None:
    @dp.message(Command("start"))
    async def cmd_start(message: Message):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 От своего имени.", callback_data="choice_user")],
            [InlineKeyboardButton(text="🥔 Анонимно (от «Картошки»).", callback_data="choice_potato")],
        ])
        if config.CRYPTOSELECTARCHY:
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
            state.set_publish_choice(user_id, "user")
            await callback.message.answer("Буду публиковать от вашего имени. Пришлите мем.")
        else:
            state.set_publish_choice(user_id, "potato")
            await callback.message.answer("Буду публиковать анонимно (от 'Картошки'). Пришлите мем.")
        await callback.answer()
