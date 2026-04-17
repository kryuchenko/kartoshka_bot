"""Функции-отправители Telegram-сообщений, связанных с жизненным циклом мема."""
import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from kartoshka.models import Meme
from kartoshka.telegram_io import send_media_message


async def update_mod_messages_with_resolution(bot: Bot, meme: Meme, resolution: str) -> None:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=resolution, callback_data="noop")]
    ])
    for chat_id, message_id in meme.mod_messages:
        try:
            await bot.edit_message_reply_markup(
                chat_id=chat_id, message_id=message_id, reply_markup=keyboard
            )
        except Exception as e:
            logging.error(f"Ошибка при обновлении сообщения для редактора {chat_id}: {e}")


async def update_user_messages_with_status(
    bot: Bot, meme: Meme, final_resolution: str = None
) -> None:
    if meme.user_id is None or not meme.user_messages:
        return

    vote_summary = meme.get_vote_summary()
    if final_resolution:
        status_text = f"{final_resolution} {vote_summary}"
    else:
        status_text = f"Голосование: {vote_summary}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=status_text, callback_data="noop")]
    ])

    for chat_id, message_id in meme.user_messages:
        try:
            await bot.edit_message_reply_markup(
                chat_id=chat_id, message_id=message_id, reply_markup=keyboard
            )
        except Exception as e:
            logging.error(f"Ошибка при обновлении сообщения для пользователя {chat_id}: {e}")


async def publish_meme(bot: Bot, meme: Meme, chat_id: int) -> bool:
    """Публикует мем в канал. Возвращает True при успехе, False при ошибке Telegram API."""
    try:
        caption = meme.get_caption()
        await send_media_message(
            telegram_bot=bot,
            chat_id=chat_id,
            content=meme.content,
            caption=caption,
        )
        return True
    except Exception as e:
        logging.error(f"Ошибка при публикации: {e}")
        return False
