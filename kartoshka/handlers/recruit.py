"""Набор криптоселектархов: кнопка-отклик из рассылки.

Выборы завершены — кнопка теперь сообщает об этом и ничего не записывает.
Историческое поведение (запись кандидата в candidates.json) сохранено под
флагом ELECTIONS_OPEN на случай повторного набора.
"""
import logging
from datetime import datetime, timezone

from aiogram import Dispatcher, F
from aiogram.types import CallbackQuery

from kartoshka import config
from kartoshka.state import AppState
from kartoshka.storage import add_candidate, load_candidates

JOIN_CALLBACK = "crypto_join"

# Набор закрыт: жребий проведён, новые отклики не принимаются.
ELECTIONS_OPEN = False


def register(dp: Dispatcher, state: AppState) -> None:
    @dp.callback_query(F.data == JOIN_CALLBACK)
    async def crypto_join(callback: CallbackQuery):
        if not ELECTIONS_OPEN:
            await callback.answer(
                "🗳 Выборы криптоселектархов завершены. Спасибо за отклик!",
                show_alert=True,
            )
            return

        user = callback.from_user
        if user.id in config.EDITOR_IDS:
            await callback.answer("Ты уже криптоселектарх 🥔", show_alert=True)
            return

        already = any(c["id"] == user.id for c in load_candidates())
        add_candidate(
            user.id,
            user.username,
            user.first_name,
            datetime.now(timezone.utc).isoformat(),
        )
        logging.info(f"Кандидат в криптоселектархи: {user.id} (@{user.username})")

        if already:
            await callback.answer("Ты уже в списке кандидатов 🥔", show_alert=True)
        else:
            await callback.answer(
                "Ты в списке кандидатов! По итогам случайно выберем троих 🥔🗳",
                show_alert=True,
            )
