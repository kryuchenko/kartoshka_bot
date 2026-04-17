import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.bot import DefaultBotProperties

from kartoshka.config import (
    API_TOKEN,
    CRYPTOSELECTARCHY,
    POST_FREQUENCY_MINUTES,
    PUBLISH_CHAT_ID,
)
from kartoshka.handlers import register_handlers
from kartoshka.notifications import publish_meme
from kartoshka.scheduler import Scheduler
from kartoshka.state import AppState
from kartoshka.storage import load_meme_counter, load_user_data

logging.basicConfig(level=logging.INFO)

if CRYPTOSELECTARCHY:
    print("Криптоселектархическая олигархия включена! (многоголосие)")
else:
    print("Единоличный Узурпатор у власти! (решение принимает один голос)")


def build_app_state() -> AppState:
    bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))

    async def on_publish(meme):
        await publish_meme(bot, meme, PUBLISH_CHAT_ID)

    scheduler = Scheduler(POST_FREQUENCY_MINUTES, bot=bot, on_publish=on_publish)

    state = AppState(
        bot=bot,
        scheduler=scheduler,
        meme_counter=max(load_meme_counter(), scheduler.get_max_meme_id()),
        user_data=load_user_data(),
    )
    return state


async def _expire_publish_choices_loop(state: AppState, interval_sec: float = 600) -> None:
    """Периодически выметает истёкшие записи user_publish_choice."""
    while True:
        await asyncio.sleep(interval_sec)
        try:
            removed = state.expire_old_choices()
            if removed:
                logging.info(f"user_publish_choice: вымело {removed} истёкших записей")
        except Exception as e:
            logging.error(f"Ошибка в cleanup-loop: {e}")


async def main() -> None:
    state = build_app_state()
    dp = Dispatcher()
    register_handlers(dp, state)

    asyncio.create_task(state.scheduler.run())
    asyncio.create_task(_expire_publish_choices_loop(state))
    await dp.start_polling(state.bot)
