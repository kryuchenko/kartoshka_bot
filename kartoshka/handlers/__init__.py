from aiogram import Dispatcher

from kartoshka.handlers import moderation, recruit, start, submit
from kartoshka.state import AppState


def register_handlers(dp: Dispatcher, state: AppState) -> None:
    start.register(dp, state)
    submit.register(dp, state)
    moderation.register(dp, state)
    recruit.register(dp, state)
