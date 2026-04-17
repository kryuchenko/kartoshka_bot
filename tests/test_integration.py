"""Integration tests: реальные handlers + моки внешних зависимостей."""
import os

os.environ.setdefault("BOT_TOKEN", "123:dummy")
os.environ.setdefault("EDITOR_IDS", "111,222")
os.environ.setdefault("PUBLISH_CHAT_ID", "12345")
os.environ.setdefault("BOT_NAME", "TestBot")
os.environ.setdefault("POST_FREQUENCY_MINUTES", "60")
os.environ.setdefault("CRYPTOSELECTARCHY", "false")
os.environ.setdefault("VOTES_TO_APPROVE", "2")
os.environ.setdefault("VOTES_TO_REJECT", "2")

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kartoshka.handlers import register_handlers
from kartoshka.state import AppState


class RecordingDispatcher:
    """Захватывает зарегистрированные handlers без реального aiogram dispatch."""

    def __init__(self):
        self.messages = []
        self.callbacks = []

    def message(self, *args, **kwargs):
        def wrap(fn):
            self.messages.append(fn)
            return fn
        return wrap

    def callback_query(self, *args, **kwargs):
        def wrap(fn):
            self.callbacks.append(fn)
            return fn
        return wrap


@pytest.fixture
def bot():
    b = AsyncMock()
    b.send_message = AsyncMock(return_value=SimpleNamespace(message_id=12345))
    b.edit_message_reply_markup = AsyncMock()
    return b


@pytest.fixture
def scheduler():
    s = MagicMock()
    s.pending_memes = {}
    s.add_pending = MagicMock(side_effect=lambda m: s.pending_memes.__setitem__(m.meme_id, m))
    s.resolve = MagicMock(side_effect=lambda mid: s.pending_memes.pop(mid, None))
    s.save_moderation = MagicMock()
    s.schedule = AsyncMock()
    return s


@pytest.fixture
def state(bot, scheduler):
    return AppState(bot=bot, scheduler=scheduler)


@pytest.fixture(autouse=True)
def no_disk_writes():
    """Не пишем на диск из тестов."""
    with patch("kartoshka.handlers.submit.save_user_data"), \
         patch("kartoshka.handlers.submit.save_meme_counter"), \
         patch("kartoshka.handlers.moderation.save_user_data"):
        yield


@pytest.fixture(autouse=True)
def isolated_config():
    """Защита от утечек состояния config через importlib.reload в других тестах."""
    with patch("kartoshka.config.VOTES_TO_APPROVE", 2), \
         patch("kartoshka.config.VOTES_TO_REJECT", 2), \
         patch("kartoshka.config.CRYPTOSELECTARCHY", False):
        yield


@pytest.fixture
def dp(state):
    d = RecordingDispatcher()
    register_handlers(d, state)
    return d


# Порядок регистрации: start → submit → moderation
def handlers_for(dp):
    return SimpleNamespace(
        cmd_start=dp.messages[0],
        handle_choice=dp.callbacks[0],
        handle_meme=dp.messages[1],
        crypto_callback=dp.callbacks[1],
        noop_callback=dp.callbacks[2],
    )


def make_message(text="hello", user_id=100, username="testuser", first_name="Test",
                 caption=None, content_type="text"):
    msg = MagicMock()
    msg.text = text
    msg.caption = caption
    msg.content_type = content_type
    msg.from_user = SimpleNamespace(id=user_id, username=username, first_name=first_name)
    msg.chat = SimpleNamespace(id=user_id)
    msg.message_id = 50
    msg.answer = AsyncMock(return_value=SimpleNamespace(message_id=51))
    return msg


def make_callback(data="", user_id=100, username="u", first_name="U"):
    cb = MagicMock()
    cb.data = data
    cb.from_user = SimpleNamespace(id=user_id, username=username, first_name=first_name)
    cb.message = MagicMock()
    cb.message.chat = SimpleNamespace(id=user_id)
    cb.message.message_id = 99
    cb.message.answer = AsyncMock()
    cb.answer = AsyncMock()
    return cb


# ===== /start и выбор публикации =====

@pytest.mark.asyncio
async def test_start_greets_uzurpator_mode(dp):
    h = handlers_for(dp)
    msg = make_message()
    await h.cmd_start(msg)
    text = msg.answer.await_args.args[0]
    assert "TestBot" in text
    assert "Единоличный Узурпатор" in text


@pytest.mark.asyncio
async def test_start_greets_crypto_mode(dp):
    h = handlers_for(dp)
    msg = make_message()
    with patch("kartoshka.config.CRYPTOSELECTARCHY", True):
        await h.cmd_start(msg)
    text = msg.answer.await_args.args[0]
    assert "Криптоселектархическая" in text


@pytest.mark.asyncio
async def test_choice_user_sets_state(dp, state):
    h = handlers_for(dp)
    cb = make_callback(data="choice_user", user_id=42)
    await h.handle_choice(cb)
    assert state.get_publish_choice(42) == "user"
    cb.answer.assert_awaited()


@pytest.mark.asyncio
async def test_choice_potato_sets_state(dp, state):
    h = handlers_for(dp)
    cb = make_callback(data="choice_potato", user_id=42)
    await h.handle_choice(cb)
    assert state.get_publish_choice(42) == "potato"


# ===== TTL для user_publish_choice =====

def test_publish_choice_expires_after_ttl(state):
    """Запись протухает через PUBLISH_CHOICE_TTL; get_publish_choice возвращает None."""
    state.set_publish_choice(7, "user")
    # Искусственно сдвигаем expires_at в прошлое
    choice, _ = state.user_publish_choice[7]
    state.user_publish_choice[7] = (choice, datetime.now(timezone.utc) - timedelta(minutes=1))

    assert state.get_publish_choice(7) is None
    # lazy-eviction: после чтения записи уже нет в dict
    assert 7 not in state.user_publish_choice


def test_expire_old_choices_sweeps_expired(state):
    """expire_old_choices удаляет все истёкшие за один проход."""
    now = datetime.now(timezone.utc)
    state.user_publish_choice[1] = ("user", now - timedelta(minutes=1))  # истёк
    state.user_publish_choice[2] = ("potato", now + timedelta(minutes=30))  # живой
    state.user_publish_choice[3] = ("user", now - timedelta(hours=1))  # истёк

    removed = state.expire_old_choices()
    assert removed == 2
    assert list(state.user_publish_choice.keys()) == [2]


# ===== Приём мема =====

@pytest.mark.asyncio
async def test_meme_without_choice_gets_error(dp, state):
    h = handlers_for(dp)
    msg = make_message(user_id=7)
    await h.handle_meme(msg)
    assert msg.answer.await_args.args[0].startswith("Сначала выберите")
    assert state.scheduler.add_pending.call_count == 0


@pytest.mark.asyncio
async def test_meme_user_mode_adds_to_scheduler(dp, state, bot):
    h = handlers_for(dp)
    state.set_publish_choice(7, "user")
    msg = make_message(text="funny joke", user_id=7)

    # Мокаем send_media_message, который handler вызывает для рассылки редакторам
    with patch("kartoshka.handlers.submit.send_media_message",
               AsyncMock(return_value=SimpleNamespace(message_id=777))):
        await h.handle_meme(msg)

    assert state.scheduler.add_pending.call_count == 1
    assert state.meme_counter == 1
    assert 1 in state.scheduler.pending_memes
    meme = state.scheduler.pending_memes[1]
    assert meme.publish_choice == "user"
    assert meme.user_id == 7


@pytest.mark.asyncio
async def test_meme_photo_user_mode(dp, state):
    h = handlers_for(dp)
    state.set_publish_choice(7, "user")
    photo = MagicMock()
    photo.file_id = "photo_id_42"
    msg = make_message(text=None, caption="my photo", user_id=7, content_type="photo")
    msg.photo = [photo]

    with patch("kartoshka.handlers.submit.send_media_message",
               AsyncMock(return_value=SimpleNamespace(message_id=777))):
        await h.handle_meme(msg)

    assert state.scheduler.add_pending.call_count == 1
    meme = list(state.scheduler.pending_memes.values())[0]
    assert meme.content.content_type == "photo"


@pytest.mark.asyncio
async def test_submission_updates_last_submission_timestamp(dp, state):
    h = handlers_for(dp)
    state.set_publish_choice(7, "user")
    msg = make_message(user_id=7)
    before = datetime.now(timezone.utc)

    with patch("kartoshka.handlers.submit.send_media_message",
               AsyncMock(return_value=SimpleNamespace(message_id=777))):
        await h.handle_meme(msg)

    ts = state.user_data["7"]["last_submission"]
    assert ts is not None and ts >= before


@pytest.mark.asyncio
async def test_meme_blocked_by_24h_limit(dp, state):
    h = handlers_for(dp)
    state.set_publish_choice(7, "user")
    state.user_data["7"] = {
        "last_submission": datetime.now(timezone.utc),
        "rejections": 0,
        "ban_until": None,
    }
    msg = make_message(user_id=7)
    await h.handle_meme(msg)
    assert "24 ч" in msg.answer.await_args.args[0]
    state.scheduler.add_pending.assert_not_called()


@pytest.mark.asyncio
async def test_meme_blocked_by_ban(dp, state):
    h = handlers_for(dp)
    state.set_publish_choice(7, "user")
    state.user_data["7"] = {
        "last_submission": None,
        "rejections": 3,
        "ban_until": datetime.now(timezone.utc) + timedelta(days=7),
    }
    msg = make_message(user_id=7)
    await h.handle_meme(msg)
    assert "изгнании" in msg.answer.await_args.args[0]


# ===== Голосование (режим Узурпатора, VOTES_*=2 но один голос решает) =====

@pytest.mark.asyncio
async def test_uzurpator_approve_schedules(dp, state):
    h = handlers_for(dp)
    from kartoshka.models import Meme
    meme = Meme(meme_id=1, user_id=7, publish_choice="user", content=make_message())
    meme.user_messages = [(7, 123)]
    state.scheduler.pending_memes[1] = meme

    cb = make_callback(data="approve_1", user_id=111)
    await h.crypto_callback(cb)

    state.scheduler.schedule.assert_awaited_once_with(meme)
    state.scheduler.resolve.assert_called_once_with(1)
    assert meme.finalized is True


@pytest.mark.asyncio
async def test_uzurpator_urgent_publishes_immediately(dp, state):
    h = handlers_for(dp)
    from kartoshka.models import Meme
    meme = Meme(meme_id=1, user_id=7, publish_choice="user", content=make_message())
    state.scheduler.pending_memes[1] = meme

    with patch("kartoshka.notifications.send_media_message", AsyncMock()) as mock_send:
        cb = make_callback(data="urgent_1", user_id=111)
        await h.crypto_callback(cb)

    mock_send.assert_awaited_once()
    state.scheduler.schedule.assert_not_awaited()
    state.scheduler.resolve.assert_called_once_with(1)
    assert meme.finalized is True


@pytest.mark.asyncio
async def test_uzurpator_reject_finalizes_and_increments_rejections(dp, state):
    h = handlers_for(dp)
    from kartoshka.models import Meme
    meme = Meme(meme_id=1, user_id=7, publish_choice="user", content=make_message())
    state.scheduler.pending_memes[1] = meme

    cb = make_callback(data="reject_1", user_id=111)
    await h.crypto_callback(cb)

    assert meme.finalized is True
    assert state.user_data["7"]["rejections"] == 1
    assert state.user_data["7"]["ban_until"] is None


# ===== Бан за 3 отклонения =====

@pytest.mark.asyncio
async def test_three_rejections_trigger_ban(dp, state, bot):
    h = handlers_for(dp)
    from kartoshka.models import Meme

    for i in range(1, 4):
        meme = Meme(meme_id=i, user_id=7, publish_choice="user", content=make_message())
        state.scheduler.pending_memes[i] = meme
        cb = make_callback(data=f"reject_{i}", user_id=111)
        await h.crypto_callback(cb)

    assert state.user_data["7"]["rejections"] == 3
    assert state.user_data["7"]["ban_until"] is not None
    # Уведомление о бане пользователю
    bot.send_message.assert_awaited()


@pytest.mark.asyncio
async def test_approval_clears_existing_ban(dp, state):
    h = handlers_for(dp)
    from kartoshka.models import Meme

    # пользователь уже забанен
    state.user_data["7"] = {
        "last_submission": None,
        "rejections": 3,
        "ban_until": datetime.now(timezone.utc) + timedelta(days=5),
    }
    meme = Meme(meme_id=1, user_id=7, publish_choice="user", content=make_message())
    state.scheduler.pending_memes[1] = meme

    await h.crypto_callback(make_callback(data="approve_1", user_id=111))

    assert state.user_data["7"]["ban_until"] is None
    assert state.user_data["7"]["rejections"] == 0


@pytest.mark.asyncio
async def test_approval_resets_rejection_counter(dp, state):
    h = handlers_for(dp)
    from kartoshka.models import Meme

    state.user_data["7"] = {"last_submission": None, "rejections": 2, "ban_until": None}

    meme = Meme(meme_id=1, user_id=7, publish_choice="user", content=make_message())
    state.scheduler.pending_memes[1] = meme
    cb = make_callback(data="approve_1", user_id=111)
    await h.crypto_callback(cb)

    assert state.user_data["7"]["rejections"] == 0


# ===== Криптоселектархический режим (нужно несколько голосов) =====

@pytest.mark.asyncio
async def test_crypto_single_approve_does_not_finalize(dp, state):
    """В crypto-режиме одного approve недостаточно (VOTES_TO_APPROVE=2)."""
    h = handlers_for(dp)
    from kartoshka.models import Meme
    meme = Meme(meme_id=1, user_id=7, publish_choice="user", content=make_message())
    state.scheduler.pending_memes[1] = meme

    with patch("kartoshka.config.CRYPTOSELECTARCHY", True):
        cb = make_callback(data="approve_1", user_id=111)
        await h.crypto_callback(cb)

    assert meme.finalized is False
    assert 1 in state.scheduler.pending_memes
    state.scheduler.schedule.assert_not_awaited()


@pytest.mark.asyncio
async def test_crypto_two_approves_finalize(dp, state):
    h = handlers_for(dp)
    from kartoshka.models import Meme
    meme = Meme(meme_id=1, user_id=7, publish_choice="user", content=make_message())
    state.scheduler.pending_memes[1] = meme

    with patch("kartoshka.config.CRYPTOSELECTARCHY", True):
        await h.crypto_callback(make_callback(data="approve_1", user_id=111))
        await h.crypto_callback(make_callback(data="approve_1", user_id=222))

    assert meme.finalized is True
    state.scheduler.schedule.assert_awaited_once_with(meme)


# ===== Noop =====

@pytest.mark.asyncio
async def test_noop_callback(dp):
    h = handlers_for(dp)
    cb = make_callback(data="noop")
    await h.noop_callback(cb)
    cb.answer.assert_awaited()


# ===== Regression: race condition при одновременных голосах =====

@pytest.mark.asyncio
async def test_concurrent_votes_finalize_once(dp, state):
    """Два одновременных голоса не должны дважды опубликовать/запланировать мем."""
    import asyncio as _asyncio
    from kartoshka.models import Meme

    meme = Meme(meme_id=1, user_id=7, publish_choice="user", content=make_message())
    state.scheduler.pending_memes[1] = meme

    cb1 = make_callback(data="urgent_1", user_id=111)
    cb2 = make_callback(data="urgent_1", user_id=222)

    with patch("kartoshka.notifications.send_media_message", AsyncMock()) as mock_send:
        await _asyncio.gather(h := handlers_for(dp).crypto_callback(cb1),
                              handlers_for(dp).crypto_callback(cb2))

    # Публикация ровно один раз, resolve ровно один раз.
    assert mock_send.await_count == 1
    assert state.scheduler.resolve.call_count == 1


# ===== Regression: silent publication loss =====

@pytest.mark.asyncio
async def test_failed_publish_keeps_meme_in_queue(dp, state):
    """Если publish упал, мем НЕ удаляется из очереди и finalized сбрасывается."""
    from kartoshka.models import Meme

    meme = Meme(meme_id=1, user_id=7, publish_choice="user", content=make_message())
    state.scheduler.pending_memes[1] = meme

    # Моделируем падение Telegram API внутри publish_meme
    with patch("kartoshka.notifications.publish_meme",
               AsyncMock(return_value=False)):
        await handlers_for(dp).crypto_callback(make_callback(data="urgent_1", user_id=111))

    # Мем остался в очереди, finalized снят, resolve НЕ вызван
    assert meme.finalized is False
    assert 1 in state.scheduler.pending_memes
    state.scheduler.resolve.assert_not_called()


# ===== Regression: HTML escape =====

def test_get_caption_escapes_html():
    """Пользовательский текст с HTML-тегами не проходит в канал как живой HTML."""
    from kartoshka.models import Meme

    msg = MagicMock()
    msg.text = "<b>Fake moderator</b> <a href='evil.com'>click</a>"
    msg.caption = None
    msg.content_type = "text"
    msg.from_user = SimpleNamespace(id=1, username="<script>", first_name="x")

    meme = Meme(meme_id=1, user_id=1, publish_choice="user", content=msg)
    caption = meme.get_caption()
    assert "<b>Fake moderator</b>" not in caption
    assert "&lt;b&gt;Fake moderator&lt;/b&gt;" in caption
    assert "<script>" not in caption  # username экранирован
    assert "&lt;script&gt;" in caption


# ===== Regression: user_id восстановлен из JSON =====

def test_from_dict_restores_user_id():
    """После рестарта бота Meme.from_dict должен восстановить user_id для не-potato мемов."""
    from kartoshka.models import Meme

    msg = MagicMock()
    msg.text = "hi"
    msg.caption = None
    msg.content_type = "text"
    msg.from_user = SimpleNamespace(id=42, username="u", first_name="U")

    meme = Meme(meme_id=1, user_id=42, publish_choice="user", content=msg)
    d = meme.to_dict()
    restored = Meme.from_dict(d)
    assert restored.user_id == 42
