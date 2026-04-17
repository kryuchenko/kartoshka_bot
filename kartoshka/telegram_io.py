from typing import Union

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from kartoshka.message_snapshot import MessageSnapshot
from kartoshka.models import Meme


async def send_media_message(
    telegram_bot: Bot,
    chat_id: int,
    content: Union[MessageSnapshot, "object"],  # либо MessageSnapshot, либо aiogram.Message
    caption: str = None,
    reply_markup=None,
):
    # Если пришёл raw Message (например, из handler'а до конвертации в snapshot)
    # — перегоняем в snapshot, чтобы ниже была единая логика по атрибутам.
    if not isinstance(content, MessageSnapshot):
        content = MessageSnapshot.from_message(content)

    if not caption:
        caption = content.caption or content.text or ""
    caption = caption or ""

    ctype = content.content_type
    if ctype == "photo":
        return await telegram_bot.send_photo(
            chat_id=chat_id,
            photo=content.photo_file_id,
            caption=caption,
            reply_markup=reply_markup,
        )
    elif ctype == "video":
        return await telegram_bot.send_video(
            chat_id=chat_id,
            video=content.video_file_id,
            caption=caption,
            reply_markup=reply_markup,
        )
    elif ctype == "animation":
        return await telegram_bot.send_animation(
            chat_id=chat_id,
            animation=content.animation_file_id,
            caption=caption,
            reply_markup=reply_markup,
        )
    elif ctype == "voice":
        return await telegram_bot.send_voice(
            chat_id=chat_id,
            voice=content.voice_file_id,
            caption=caption,
            reply_markup=reply_markup,
        )
    elif ctype == "video_note":
        return await telegram_bot.send_video_note(
            chat_id=chat_id,
            video_note=content.video_note_file_id,
            reply_markup=reply_markup,
        )
    else:
        return await telegram_bot.send_message(
            chat_id=chat_id,
            text=caption,
            reply_markup=reply_markup,
        )


def build_mod_keyboard(meme: Meme, mod_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для модератора mod_id: выбранная кнопка с «➤»."""
    vote = meme.votes.get(str(mod_id))
    actions = [
        ("approve", "✅Одбр."),
        ("urgent", "⚡Срч."),
        ("reject", "❌Отк."),
    ]
    buttons = []
    for action_key, label in actions:
        text = f"➤ {label}" if vote == action_key else label
        buttons.append(
            InlineKeyboardButton(text=text, callback_data=f"{action_key}_{meme.meme_id}")
        )
    return InlineKeyboardMarkup(inline_keyboard=[buttons])
