import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from aiogram import Dispatcher, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from kartoshka.config import EDITOR_IDS
from kartoshka.message_snapshot import MessageSnapshot
from kartoshka.models import Meme
from kartoshka.state import AppState
from kartoshka.storage import save_meme_counter, save_user_data
from kartoshka.telegram_io import send_media_message


def check_user_limits(user_id: int, now: datetime, state: AppState) -> Optional[str]:
    """Проверяет бан и 24h-лимит. Возвращает текст отказа или None если всё ок."""
    ud = state.user_data.setdefault(str(user_id), {
        "last_submission": None,
        "rejections": 0,
        "ban_until": None,
    })

    if ud["ban_until"] and now < ud["ban_until"]:
        until = ud["ban_until"].strftime("%d.%m.%Y")
        return f"Сорри, ты у нас в изгнании до {until}, мемы отправлять нельзя."

    if ud["last_submission"] and now - ud["last_submission"] < timedelta(hours=24):
        nt = ud["last_submission"] + timedelta(hours=24)
        return f"Ты уже отправлял мем в последние 24 ч. Попробуй после {nt.strftime('%H:%M %d.%m.%Y')}."

    return None


def register(dp: Dispatcher, state: AppState) -> None:
    @dp.message(F.content_type.in_(["text", "photo", "video", "animation", "voice", "video_note"]))
    async def handle_meme_suggestion(message: Message):
        user_id = message.from_user.id
        chosen_mode = state.get_publish_choice(user_id)
        if chosen_mode is None:
            await message.answer("Сначала выберите способ публикации с помощью команды /start.")
            return

        now = datetime.now(timezone.utc)
        rejection = check_user_limits(user_id, now, state)
        if rejection:
            await message.answer(rejection)
            return

        state.user_data[str(user_id)]["last_submission"] = now
        save_user_data(state.user_data)

        state.meme_counter += 1
        real_user_id: Optional[int] = user_id

        # Выжимаем нужные поля из aiogram.Message в лёгкий snapshot — иначе Meme
        # будет держать 109-полевой pydantic-граф в памяти до 3 дней.
        snapshot = MessageSnapshot.from_message(message)
        meme = Meme(
            meme_id=state.meme_counter,
            user_id=real_user_id,
            publish_choice=chosen_mode,
            content=snapshot,
        )
        state.scheduler.add_pending(meme)
        save_meme_counter(state.meme_counter)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅Одбр.", callback_data=f"approve_{meme.meme_id}"),
                InlineKeyboardButton(text="⚡Срч.", callback_data=f"urgent_{meme.meme_id}"),
                InlineKeyboardButton(text="❌Отк.", callback_data=f"reject_{meme.meme_id}"),
            ]
        ])

        if chosen_mode == "user":
            if message.from_user.username:
                from_text = f"@{message.from_user.username}"
            else:
                from_text = f"{message.from_user.id}"
        else:
            from_text = "Картошка"

        user_text = message.caption if message.caption else message.text
        display_text = user_text if user_text else "[Без текста]"
        info_text = (
            f"Мем ID: {meme.meme_id}\n\n{display_text}\n\nОт: {from_text}\n"
            f"Публикация как: {chosen_mode}"
        )

        for crypto_id in EDITOR_IDS:
            try:
                sent_msg = await send_media_message(
                    telegram_bot=state.bot,
                    chat_id=crypto_id,
                    content=message,
                    caption=info_text,
                    reply_markup=keyboard,
                )
                meme.mod_messages.append((crypto_id, sent_msg.message_id))
            except Exception as e:
                logging.error(f"Не удалось отправить сообщение редактору {crypto_id}: {e}")

        user_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"Голосование: {meme.get_vote_summary()}", callback_data="noop")]
        ])
        user_msg = await message.answer("Ваш мем отправлен на модерацию.", reply_markup=user_keyboard)

        if meme.user_id is not None:
            meme.user_messages.append((meme.user_id, user_msg.message_id))
