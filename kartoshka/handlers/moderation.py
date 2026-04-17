import logging
from datetime import datetime, timedelta, timezone

from aiogram import Dispatcher, F
from aiogram.types import CallbackQuery

from kartoshka import config, notifications
from kartoshka.config import PUBLISH_CHAT_ID
from kartoshka.models import Meme
from kartoshka.state import AppState
from kartoshka.storage import save_user_data
from kartoshka.telegram_io import build_mod_keyboard


def _default_user_data():
    return {"last_submission": None, "rejections": 0, "ban_until": None}


def _reset_rejections(user_id, state: AppState) -> None:
    if not user_id:
        return
    ud = state.user_data.setdefault(str(user_id), _default_user_data())
    ud["rejections"] = 0
    ud["ban_until"] = None
    save_user_data(state.user_data)


async def _increment_rejections_and_maybe_ban(user_id, state: AppState) -> None:
    if not user_id:
        return
    ud = state.user_data.setdefault(str(user_id), _default_user_data())
    ud["rejections"] += 1

    if ud["rejections"] >= 3:
        ud["ban_until"] = datetime.now(timezone.utc) + timedelta(days=14)

    # Сначала коммитим изменения на диск — важнее чем уведомление.
    save_user_data(state.user_data)

    # Уведомление пользователя о бане может не пройти (юзер заблокировал бота) — не фейлимся.
    if ud["rejections"] >= 3:
        until = ud["ban_until"].strftime("%d.%m.%Y")
        try:
            await state.bot.send_message(user_id, f"Сорри, ты у нас в изгнании до {until}.")
        except Exception as e:
            logging.error(f"Не удалось уведомить пользователя {user_id} о бане: {e}")


async def _finalize_meme(meme: Meme, action: str, state: AppState) -> None:
    """Завершает судьбу мема. Caller уже установил meme.finalized=True для защиты от гонки.

    Если публикация проваливается — сбрасываем finalized и оставляем мем в очереди для повтора.
    """
    if action == "urgent":
        published = await notifications.publish_meme(state.bot, meme, PUBLISH_CHAT_ID)
        if not published:
            # Отменяем claim — пусть модераторы попробуют ещё раз.
            meme.finalized = False
            await notifications.update_mod_messages_with_resolution(
                state.bot, meme, "❗ Ошибка публикации — попробуйте ещё раз"
            )
            return
        resolution = "⚡ Одбр.срч."
        _reset_rejections(meme.user_id, state)
    elif action == "approve":
        resolution = "✅ Одбр."
        await state.scheduler.schedule(meme)
        _reset_rejections(meme.user_id, state)
    else:  # reject
        resolution = "❌ Отк."
        await _increment_rejections_and_maybe_ban(meme.user_id, state)

    await notifications.update_user_messages_with_status(state.bot, meme, resolution)
    resolution_with_summary = f"{resolution} {meme.get_vote_summary()}"
    await notifications.update_mod_messages_with_resolution(state.bot, meme, resolution_with_summary)
    state.scheduler.resolve(meme.meme_id)


def register(dp: Dispatcher, state: AppState) -> None:
    @dp.callback_query(F.data.startswith(("approve_", "urgent_", "reject_")))
    async def crypto_callback(callback: CallbackQuery):
        action, meme_id_str = callback.data.split("_", 1)
        meme_id = int(meme_id_str)
        if meme_id not in state.scheduler.pending_memes:
            await callback.answer("Заявка не найдена или уже обработана.")
            return

        meme = state.scheduler.pending_memes[meme_id]
        crypto_id = callback.from_user.id
        meme.add_vote(crypto_id, action)
        state.scheduler.save_moderation()

        # Атомарно: решаем финализировать и ставим claim ДО любого await.
        # Это защищает от гонки, когда два callback-а одновременно приходят к финализации.
        final_action = None
        if not meme.finalized:
            if not config.CRYPTOSELECTARCHY:
                final_action = action
            elif meme.is_approved():
                final_action = "urgent" if meme.is_urgent() else "approve"
            elif meme.is_rejected():
                final_action = "reject"
            if final_action is not None:
                meme.finalized = True  # ← атомарный claim, до первого await

        await notifications.update_user_messages_with_status(state.bot, meme)
        await callback.answer("Ваш голос учтен.", show_alert=False)

        new_kb = build_mod_keyboard(meme, crypto_id)
        await state.bot.edit_message_reply_markup(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            reply_markup=new_kb,
        )

        if final_action is not None:
            await _finalize_meme(meme, final_action, state)

    @dp.callback_query(lambda c: c.data == "noop")
    async def noop_callback(callback: CallbackQuery):
        await callback.answer("Голосование завершено, эта кнопка не активна.", show_alert=True)
