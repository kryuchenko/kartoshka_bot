# Kartoshka Bot 🥔

[![CI](https://github.com/kryuchenko/kartoshka_bot/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/kryuchenko/kartoshka_bot/actions/workflows/tests.yml)
[![Coverage](https://img.shields.io/badge/Coverage-77%25-yellow)](https://github.com/kryuchenko/kartoshka_bot/actions/workflows/tests.yml)

Telegram-бот для модерации и публикации мемов через голосование редакторов.

## Возможности

- Приём мемов: текст, фото, видео, GIF, voice, video-note.
- Публикация от своего имени или анонимно («от Анонимной \<Металлической\> Картошки»).
- Два режима модерации:
  - **Узурпатор** — один модератор решает.
  - **Криптоселектархия** — решение большинством голосов.
- Urgent-публикация: если ≥51% голосов «⚡ Срочно» — мем уходит в канал немедленно, иначе в очередь.
- Очередь публикации с интервалом, паузой ночью (до 07:00 UTC).
- Интерактивный виджет статуса голосования — одно сообщение, обновляется в реальном времени.
- Автобан автора на 14 дней после 3 отклонений подряд.
- 24h rate-limit на отправку мемов с одного пользователя.

## Переменные окружения

Создай файл `.env` в корне:

| Переменная | Пример | Описание |
|---|---|---|
| `BOT_TOKEN` | `123:ABC...` | Токен от [@BotFather](https://t.me/BotFather) |
| `EDITOR_IDS` | `1,2,3` | Telegram-ID модераторов, через запятую |
| `PUBLISH_CHAT_ID` | `-1001234567890` | ID канала для публикации |
| `BOT_NAME` | `Картошка` | Имя в приветствии |
| `POST_FREQUENCY_MINUTES` | `180` | Интервал между постами из очереди |
| `CRYPTOSELECTARCHY` | `true` / `false` | Режим коллективного голосования |
| `VOTES_TO_APPROVE` | `3` | Голосов «Одобрить» для публикации |
| `VOTES_TO_REJECT` | `3` | Голосов «Отклонить» для отказа |

## Установка (systemd)

```bash
git clone git@github.com:kryuchenko/kartoshka_bot.git
cd kartoshka_bot
$EDITOR .env                      # заполнить переменные из таблицы выше
sudo ./setup_kartoshka_service.sh # venv + systemd, запуск при старте системы
sudo systemctl status kartoshka_bot
```

Управление:

```bash
sudo systemctl restart kartoshka_bot
sudo systemctl stop kartoshka_bot
sudo systemctl disable kartoshka_bot
```

## Разработка

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python kartoshka_bot.py            # локальный запуск
pytest tests/                      # 90 тестов
```

## Структура проекта

```
kartoshka_bot.py           entrypoint-shim: asyncio.run(main())
kartoshka/
├── main.py                build_app_state() + main()
├── state.py               AppState (bot, scheduler, meme_counter, user_data, user_publish_choice)
├── config.py              env-переменные
├── constants.py           METALS_AND_TOXINS + имена JSON-файлов
├── models.py              Meme
├── message_snapshot.py    MessageSnapshot — лёгкий снимок aiogram.Message
├── storage.py             JSON I/O (meme_counter, user_data)
├── scheduler.py           Scheduler с DI (bot, on_publish)
├── telegram_io.py         send_media_message, build_mod_keyboard
├── notifications.py       publish_meme, update_user/mod_messages_with_status
└── handlers/
    ├── start.py           /start + выбор публикации
    ├── submit.py          приём мема + check_user_limits
    └── moderation.py      голоса модераторов + финализация
```

## Лицензия

MIT — см. [LICENSE](LICENSE).
