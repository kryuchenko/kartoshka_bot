#!/usr/bin/env python3
"""Одноразовая рассылка приглашения в криптоселектархи.

Использование (из каталога проекта, в venv):
    python3 broadcast_recruit.py --test         # только TEST_ID
    python3 broadcast_recruit.py --dry-run       # показать аудиторию, не слать
    python3 broadcast_recruit.py --go            # боевая рассылка по 51 «чистому»

Берёт BOT_TOKEN из .env. Аудитория «чистых» считается из user_data.json:
rejections == 0, есть last_submission, не в бане.
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from aiogram import Bot
from aiogram.client.bot import DefaultBotProperties
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from kartoshka import config
from kartoshka.handlers.recruit import JOIN_CALLBACK

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("broadcast")

# --- ПОДСТАВЬ свой Telegram id для теста ---
TEST_ID = None  # выставляется через --test-id

MESSAGE = (
    "🥔🗳 <b>Криптоселектархия ищет новых селектархов!</b>\n\n"
    "Ты присылал(а) мемы в «Секту свидетелей хипстот» — и делал(а) это достойно.\n\n"
    "Нам нужны новые <b>криптоселектархи</b> — те, кто голосует за публикацию "
    "мемов и вершит судьбу контента.\n\n"
    "Если готов(а) принять бремя власти — жми кнопку ниже. "
    "По итогам мы <b>случайным жребием</b> выберем троих из всех откликнувшихся.\n\n"
    "Власть — случайности. Слава Картошке!"
)

KEYBOARD = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🗳 Я готов стать криптоселектархом", callback_data=JOIN_CALLBACK)]
])


def clean_audience() -> list:
    raw = json.load(open("user_data.json", encoding="utf-8"))
    now = datetime.now(timezone.utc)
    ids = []
    for uid, ud in raw.items():
        if not ud.get("last_submission"):
            continue
        if ud.get("rejections", 0) != 0:
            continue
        if int(uid) in config.EDITOR_IDS:
            continue  # действующие редакторы
        if int(uid) == 12345:
            continue  # тестовый аккаунт
        bu = ud.get("ban_until")
        if bu and datetime.fromisoformat(bu) > now:
            continue
        ids.append(int(uid))
    return ids


async def send_to(bot: Bot, uid: int) -> str:
    try:
        await bot.send_message(uid, MESSAGE, reply_markup=KEYBOARD)
        return "ok"
    except Exception as e:
        return f"FAIL: {type(e).__name__}: {e}"


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="слать только на --test-id")
    ap.add_argument("--test-id", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--go", action="store_true")
    args = ap.parse_args()

    load_dotenv()
    token = os.getenv("BOT_TOKEN")

    audience = clean_audience()
    log.info(f"Аудитория «чистых»: {len(audience)} id")

    if args.dry_run:
        log.info("DRY-RUN, никому не отправляю. Список id:")
        log.info(", ".join(map(str, audience)))
        return

    if args.test:
        if not args.test_id:
            log.error("Укажи --test-id <твой_telegram_id>")
            sys.exit(1)
        targets = [args.test_id]
    elif args.go:
        targets = audience
    else:
        log.error("Нужен один из флагов: --test / --dry-run / --go")
        sys.exit(1)

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode="HTML"))
    ok = fail = 0
    try:
        for i, uid in enumerate(targets, 1):
            res = await send_to(bot, uid)
            if res == "ok":
                ok += 1
                log.info(f"[{i}/{len(targets)}] {uid}: ✅")
            else:
                fail += 1
                log.info(f"[{i}/{len(targets)}] {uid}: ❌ {res}")
            await asyncio.sleep(0.4)  # бережём rate limit
    finally:
        await bot.session.close()
    log.info(f"ИТОГО: доставлено {ok}, ошибок {fail}")


if __name__ == "__main__":
    asyncio.run(main())
