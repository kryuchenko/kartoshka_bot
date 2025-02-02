import asyncio
import math
import random
from datetime import datetime, timezone, timedelta
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import importlib

# Предполагается, что исходный код находится в файле kartoshka_bot.py.
import kartoshka_bot as bot
from kartoshka_bot import (
    send_media_message,
    Meme,
    Scheduler,
    publish_meme,
    remove_voting_buttons,
    METALS_AND_TOXINS,
    VOTES_TO_APPROVE,
    VOTES_TO_REJECT
)

# ----- Вспомогательные классы для тестирования -----
class DummyUser:
    def __init__(self, username=None, id=12345):
        self.username = username
        self.id = id

class DummyMessage:
    def __init__(self, text="", caption="", photo=None, video=None, animation=None, voice=None, video_note=None, from_user=None):
        self.text = text
        self.caption = caption
        self.photo = photo
        self.video = video
        self.animation = animation
        self.voice = voice
        self.video_note = video_note
        self.from_user = from_user or DummyUser()

# ----- Тесты для функции send_media_message -----
@pytest.mark.asyncio
async def test_send_media_message_photo():
    fake_bot = MagicMock(spec=bot.Bot)
    fake_bot.send_photo = AsyncMock(return_value="photo_message_result")
    dummy_photo = MagicMock()
    dummy_photo.file_id = "photo_file_123"
    msg = DummyMessage(caption="Test caption", photo=[dummy_photo], text="fallback text")
    result = await send_media_message(telegram_bot=fake_bot, chat_id=111, content=msg)
    fake_bot.send_photo.assert_awaited_once_with(
        chat_id=111,
        photo="photo_file_123",
        caption="Test caption",
        reply_markup=None
    )
    assert result == "photo_message_result"

@pytest.mark.asyncio
async def test_send_media_message_video():
    fake_bot = MagicMock(spec=bot.Bot)
    fake_bot.send_video = AsyncMock(return_value="video_message_result")
    dummy_video = MagicMock()
    dummy_video.file_id = "video_file_123"
    msg = DummyMessage(caption="Video caption", video=dummy_video, text="fallback text")
    result = await send_media_message(telegram_bot=fake_bot, chat_id=222, content=msg)
    fake_bot.send_video.assert_awaited_once_with(
        chat_id=222,
        video="video_file_123",
        caption="Video caption",
        reply_markup=None
    )
    assert result == "video_message_result"

@pytest.mark.asyncio
async def test_send_media_message_animation():
    fake_bot = MagicMock(spec=bot.Bot)
    fake_bot.send_animation = AsyncMock(return_value="animation_message_result")
    dummy_animation = MagicMock()
    dummy_animation.file_id = "animation_file_123"
    msg = DummyMessage(caption="Animation caption", animation=dummy_animation, text="fallback text")
    result = await send_media_message(telegram_bot=fake_bot, chat_id=333, content=msg)
    fake_bot.send_animation.assert_awaited_once_with(
        chat_id=333,
        animation="animation_file_123",
        caption="Animation caption",
        reply_markup=None
    )
    assert result == "animation_message_result"

@pytest.mark.asyncio
async def test_send_media_message_voice():
    fake_bot = MagicMock(spec=bot.Bot)
    fake_bot.send_voice = AsyncMock(return_value="voice_message_result")
    dummy_voice = MagicMock()
    dummy_voice.file_id = "voice_file_123"
    msg = DummyMessage(caption="Voice caption", voice=dummy_voice, text="fallback text")
    result = await send_media_message(telegram_bot=fake_bot, chat_id=444, content=msg)
    fake_bot.send_voice.assert_awaited_once_with(
        chat_id=444,
        voice="voice_file_123",
        caption="Voice caption",
        reply_markup=None
    )
    assert result == "voice_message_result"

@pytest.mark.asyncio
async def test_send_media_message_video_note():
    fake_bot = MagicMock(spec=bot.Bot)
    fake_bot.send_video_note = AsyncMock(return_value="video_note_message_result")
    dummy_video_note = MagicMock()
    dummy_video_note.file_id = "video_note_file_123"
    msg = DummyMessage(video_note=dummy_video_note, text="fallback text")
    result = await send_media_message(telegram_bot=fake_bot, chat_id=555, content=msg)
    fake_bot.send_video_note.assert_awaited_once_with(
        chat_id=555,
        video_note="video_note_file_123",
        reply_markup=None
    )
    assert result == "video_note_message_result"

@pytest.mark.asyncio
async def test_send_media_message_text_fallback():
    fake_bot = MagicMock(spec=bot.Bot)
    fake_bot.send_message = AsyncMock(return_value="text_message_result")
    msg = DummyMessage(caption="", text="Simple text message")
    result = await send_media_message(telegram_bot=fake_bot, chat_id=666, content=msg)
    fake_bot.send_message.assert_awaited_once_with(
        chat_id=666,
        text="Simple text message",
        reply_markup=None
    )
    assert result == "text_message_result"

# ----- Тесты для класса Meme -----
def test_meme_add_and_count_votes():
    msg = DummyMessage(text="Test meme", caption="Test meme caption", from_user=DummyUser(username="TestUser", id=1001))
    meme = Meme(1, 1001, "user", msg)
    assert meme.add_vote(2001, "approve") is None
    assert meme.count_votes("approve") == 1
    assert meme.add_vote(2002, "urgent") is None
    assert meme.count_votes("approve") == 2
    assert meme.count_votes("urgent") == 1
    prev = meme.add_vote(2001, "reject")
    assert prev == "approve"
    assert meme.count_votes("approve") == 1
    assert meme.count_votes("reject") == 1

def test_meme_is_approved_and_urgent(monkeypatch):
    monkeypatch.setattr(bot, "VOTES_TO_APPROVE", 3)
    monkeypatch.setattr(bot, "VOTES_TO_REJECT", 2)
    msg = DummyMessage(text="Meme for approval", caption="Approval test", from_user=DummyUser(username="Approver", id=1002))
    meme = Meme(2, 1002, "user", msg)
    meme.add_vote(3001, "approve")
    assert not meme.is_approved()
    meme.add_vote(3002, "urgent")
    assert not meme.is_approved()
    meme.add_vote(3003, "approve")
    assert meme.is_approved()
    meme_urgent = Meme(3, 1003, "user", msg)
    meme_urgent.add_vote(4001, "urgent")
    assert not meme_urgent.is_urgent()
    meme_urgent.add_vote(4002, "urgent")
    assert meme_urgent.is_urgent()
    meme_reject = Meme(4, 1004, "user", msg)
    meme_reject.add_vote(5001, "reject")
    assert not meme_reject.is_rejected()
    meme_reject.add_vote(5002, "reject")
    assert meme_reject.is_rejected()

def test_meme_get_caption_user():
    user = DummyUser(username="TestUser", id=1010)
    msg = DummyMessage(caption="User meme caption", text="User meme text", from_user=user)
    meme = Meme(10, 1010, "user", msg)
    caption = meme.get_caption()
    assert "Мем от @TestUser" in caption
    assert "User meme caption" in caption or "User meme text" in caption

def test_meme_get_caption_anonymous(monkeypatch):
    user = DummyUser(username="IgnoredUser", id=2020)
    msg = DummyMessage(caption="Anonymous meme caption", text="Anonymous meme text", from_user=user)
    meme = Meme(11, 2020, "potato", msg)
    monkeypatch.setattr(random, "choice", lambda x: "Талиевая")
    caption = meme.get_caption()
    expected_prefix = "<tg-spoiler>Мем от Анонимной Талиевая Картошки</tg-spoiler>"
    assert expected_prefix in caption
    assert "Anonymous meme caption" in caption or "Anonymous meme text" in caption

def test_meme_get_caption_empty():
    user = DummyUser(username="UserEmpty", id=303)
    msg = DummyMessage(caption="", text="", from_user=user)
    meme = Meme(99, 303, "user", msg)
    caption = meme.get_caption()
    assert caption == "Мем от @UserEmpty"

# ----- Тесты для планировщика публикаций (Scheduler) -----
@pytest.mark.asyncio
async def test_scheduler_schedule_immediate(monkeypatch):
    scheduler = Scheduler(1)
    scheduler.last_published_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    msg = DummyMessage(text="Scheduler test", caption="Scheduler test caption", from_user=DummyUser(username="SchedulerUser", id=3030))
    meme = Meme(20, 3030, "user", msg)
    fake_publish = AsyncMock()
    monkeypatch.setattr(bot, "publish_meme", fake_publish)
    fake_send = AsyncMock()
    monkeypatch.setattr(bot.bot, "send_message", fake_send)
    await scheduler.schedule(meme)
    fake_publish.assert_awaited_once_with(meme)
    fake_send.assert_awaited_once_with(meme.user_id, "Ваш мем одобрен и опубликован немедленно!")
    assert scheduler.scheduled_posts == []

@pytest.mark.asyncio
async def test_scheduler_schedule_delayed(monkeypatch):
    scheduler = Scheduler(5)
    scheduler.last_published_time = datetime.now(timezone.utc)
    msg = DummyMessage(text="Delayed schedule test", caption="Delayed caption", from_user=DummyUser(username="DelayedUser", id=4040))
    meme = Meme(21, 4040, "user", msg)
    fake_send = AsyncMock()
    monkeypatch.setattr(bot.bot, "send_message", fake_send)
    fake_publish = AsyncMock()
    monkeypatch.setattr(bot, "publish_meme", fake_publish)
    await scheduler.schedule(meme)
    fake_publish.assert_not_awaited()
    assert len(scheduler.scheduled_posts) == 1
    scheduled_time, scheduled_meme = scheduler.scheduled_posts[0]
    assert scheduled_meme == meme
    fake_send.assert_awaited_once()
    sent_text = fake_send.await_args[0][1]
    assert "Ориентировочное время публикации:" in sent_text
    assert "через" in sent_text

@pytest.mark.asyncio
async def test_scheduler_run(monkeypatch):
    scheduler = Scheduler(1)
    msg = DummyMessage(text="Run test", caption="Run caption", from_user=DummyUser(username="RunUser", id=5050))
    meme = Meme(30, 5050, "user", msg)
    scheduler.scheduled_posts.append((datetime.now(timezone.utc) - timedelta(seconds=1), meme))
    fake_publish = AsyncMock()
    monkeypatch.setattr(bot, "publish_meme", fake_publish)
    run_task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.2)
    run_task.cancel()
    try:
        await run_task
    except asyncio.CancelledError:
        pass
    fake_publish.assert_awaited_once_with(meme)
    assert scheduler.scheduled_posts == []

# ----- Тесты для функции remove_voting_buttons -----
@pytest.mark.asyncio
async def test_remove_voting_buttons(monkeypatch):
    msg = DummyMessage(text="Test mod", caption="Test mod caption", from_user=DummyUser(id=6060))
    meme = Meme(40, 6060, "user", msg)
    meme.mod_messages = [(111, 10), (222, 20)]
    fake_edit = AsyncMock()
    async def fake_edit_side_effect(chat_id, message_id, reply_markup):
        if chat_id == 222:
            raise Exception("Edit failed")
        return "edited"
    fake_edit.side_effect = fake_edit_side_effect
    monkeypatch.setattr(bot.bot, "edit_message_reply_markup", fake_edit)
    await remove_voting_buttons(meme)
    assert fake_edit.await_count == 2

# ----- Тест для функции publish_meme -----
@pytest.mark.asyncio
async def test_publish_meme(monkeypatch):
    msg = DummyMessage(text="Publish test", caption="Publish caption", from_user=DummyUser(username="Publisher", id=7070))
    meme = Meme(50, 7070, "user", msg)
    fake_send_media = AsyncMock(return_value="published_message")
    monkeypatch.setattr(bot, "send_media_message", fake_send_media)
    await publish_meme(meme)
    fake_send_media.assert_awaited_once_with(
        telegram_bot=bot.bot,
        chat_id=bot.PUBLISH_CHAT_ID,
        content=meme.content,
        caption=meme.get_caption()
    )
    fake_send_media.side_effect = Exception("Publish error")
    with patch.object(bot.logging, "error") as fake_logger:
        await publish_meme(meme)
        fake_logger.assert_called()

# ----- Дополнительные тесты для покрытия веток модуля -----
def test_missing_env_vars(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "")
    monkeypatch.setenv("EDITOR_IDS", "123")
    monkeypatch.setenv("PUBLISH_CHAT_ID", "123")
    monkeypatch.setenv("BOT_NAME", "TestBot")
    monkeypatch.setenv("POST_FREQUENCY_MINUTES", "1")
    monkeypatch.setenv("CRYPTOSELECTARCHY", "false")
    monkeypatch.setenv("VOTES_TO_APPROVE", "1")
    monkeypatch.setenv("VOTES_TO_REJECT", "1")
    with pytest.raises(ValueError, match="Отсутствуют обязательные переменные окружения"):
        importlib.reload(bot)

def test_print_environment_mode_crypto(monkeypatch, capsys):
    # Устанавливаем корректный BOT_TOKEN (например, "123:dummy") чтобы не выбрасывалась ошибка валидации
    monkeypatch.setenv("BOT_TOKEN", "123:dummy")
    monkeypatch.setenv("EDITOR_IDS", "111,222")
    monkeypatch.setenv("PUBLISH_CHAT_ID", "123")
    monkeypatch.setenv("BOT_NAME", "TestBot")
    monkeypatch.setenv("POST_FREQUENCY_MINUTES", "1")
    monkeypatch.setenv("CRYPTOSELECTARCHY", "true")
    monkeypatch.setenv("VOTES_TO_APPROVE", "1")
    monkeypatch.setenv("VOTES_TO_REJECT", "1")
    importlib.reload(bot)
    captured = capsys.readouterr().out
    assert "Криптоселектархическая олигархия включена!" in captured

def test_print_environment_mode_nocrypto(monkeypatch, capsys):
    monkeypatch.setenv("BOT_TOKEN", "123:dummy")
    monkeypatch.setenv("EDITOR_IDS", "111,222")
    monkeypatch.setenv("PUBLISH_CHAT_ID", "123")
    monkeypatch.setenv("BOT_NAME", "TestBot")
    monkeypatch.setenv("POST_FREQUENCY_MINUTES", "1")
    monkeypatch.setenv("CRYPTOSELECTARCHY", "false")
    monkeypatch.setenv("VOTES_TO_APPROVE", "1")
    monkeypatch.setenv("VOTES_TO_REJECT", "1")
    importlib.reload(bot)
    captured = capsys.readouterr().out
    assert "Единоличный Узурпатор у власти." in captured

@pytest.mark.asyncio
async def test_main(monkeypatch):
    dp_instance = MagicMock()
    dp_instance.start_polling = AsyncMock(return_value=None)
    monkeypatch.setattr(bot, "Dispatcher", lambda: dp_instance)
    await bot.main()
    dp_instance.start_polling.assert_called_once_with(bot.bot)
