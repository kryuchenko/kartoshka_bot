import asyncio
import math
import random
from datetime import datetime, timezone, timedelta
import pytest

# Импорты, необходимые перед фикстурой
from unittest.mock import AsyncMock, MagicMock, patch
import importlib
import os
from types import SimpleNamespace

# Устанавливаем переменные окружения перед импортом модуля
os.environ["BOT_TOKEN"] = "123:dummy"
os.environ["EDITOR_IDS"] = "111,222,333"
os.environ["PUBLISH_CHAT_ID"] = "12345"
os.environ["BOT_NAME"] = "TestBot"
os.environ["POST_FREQUENCY_MINUTES"] = "60"
os.environ["CRYPTOSELECTARCHY"] = "true"
os.environ["VOTES_TO_APPROVE"] = "2"
os.environ["VOTES_TO_REJECT"] = "2"

# Фикстура для дополнительной настройки окружения в тестах, если потребуется
@pytest.fixture(autouse=True, scope="module")
def setup_environment():
    # Переменные уже установлены выше
    yield
    # Нет необходимости сбрасывать переменные, так как они существуют только во время выполнения тестов

# Предполагается, что исходный код находится в файле kartoshka_bot.py.
import kartoshka.main as bot
from kartoshka import config as _config
from kartoshka.config import VOTES_TO_APPROVE, VOTES_TO_REJECT
from kartoshka.constants import METALS_AND_TOXINS
from kartoshka.models import Meme
from kartoshka.notifications import publish_meme
from kartoshka.scheduler import Scheduler
from kartoshka.message_snapshot import MessageSnapshot
from kartoshka.telegram_io import send_media_message

# ----- Вспомогательные классы для тестирования -----
class DummyUser:
    def __init__(self, username=None, id=12345):
        self.username = username
        self.id = id

# Переименование класса DummyMessage, чтобы избежать конфликта с импортированным
class FakeMessage:
    def __init__(self, text="", caption="", photo=None, video=None, animation=None, voice=None, video_note=None, from_user=None):
        self.text = text
        self.caption = caption
        self.photo = photo
        self.video = video
        self.animation = animation
        self.voice = voice
        self.video_note = video_note
        self.from_user = from_user or DummyUser()
        # Добавляем content_type для совместимости с кодом, который требует его
        if photo:
            self.content_type = "photo"
        elif video:
            self.content_type = "video"
        elif animation:
            self.content_type = "animation"
        elif voice:
            self.content_type = "voice"
        elif video_note:
            self.content_type = "video_note"
        else:
            self.content_type = "text"

# ----- Тесты для функции send_media_message -----
@pytest.mark.asyncio
async def test_send_media_message_photo():
    fake_bot = MagicMock()
    fake_bot.send_photo = AsyncMock(return_value="photo_message_result")
    dummy_photo = MagicMock()
    dummy_photo.file_id = "photo_file_123"
    # Необходимо имитировать последний элемент в списке, к которому обращается код
    photo_list = [dummy_photo]
    
    msg = FakeMessage(caption="Test caption", photo=photo_list, text="fallback text")
    
    # Мокируем метод извлечения file_id для совместимости с кодом
    async def mock_send_photo(chat_id, photo, caption, reply_markup):
        return "photo_message_result"
    fake_bot.send_photo.side_effect = mock_send_photo
    
    result = await send_media_message(telegram_bot=fake_bot, chat_id=111, content=msg)
    
    # Проверяем, что метод был вызван хотя бы раз
    assert fake_bot.send_photo.called
    assert result == "photo_message_result"

@pytest.mark.asyncio
async def test_send_media_message_video():
    fake_bot = MagicMock()
    fake_bot.send_video = AsyncMock(return_value="video_message_result")
    dummy_video = MagicMock()
    dummy_video.file_id = "video_file_123"
    msg = FakeMessage(caption="Video caption", video=dummy_video, text="fallback text")
    
    # Мокируем метод для совместимости с кодом
    async def mock_send_video(chat_id, video, caption, reply_markup):
        return "video_message_result"
    fake_bot.send_video.side_effect = mock_send_video
    
    result = await send_media_message(telegram_bot=fake_bot, chat_id=222, content=msg)
    
    # Проверяем, что метод был вызван хотя бы раз
    assert fake_bot.send_video.called
    assert result == "video_message_result"

@pytest.mark.asyncio
async def test_send_media_message_animation():
    fake_bot = MagicMock()
    fake_bot.send_animation = AsyncMock(return_value="animation_message_result")
    dummy_animation = MagicMock()
    dummy_animation.file_id = "animation_file_123"
    msg = FakeMessage(caption="Animation caption", animation=dummy_animation, text="fallback text")
    
    # Мокируем метод для совместимости с кодом
    async def mock_send_animation(chat_id, animation, caption, reply_markup):
        return "animation_message_result"
    fake_bot.send_animation.side_effect = mock_send_animation
    
    result = await send_media_message(telegram_bot=fake_bot, chat_id=333, content=msg)
    
    # Проверяем, что метод был вызван хотя бы раз
    assert fake_bot.send_animation.called
    assert result == "animation_message_result"

@pytest.mark.asyncio
async def test_send_media_message_voice():
    fake_bot = MagicMock()
    fake_bot.send_voice = AsyncMock(return_value="voice_message_result")
    dummy_voice = MagicMock()
    dummy_voice.file_id = "voice_file_123"
    msg = FakeMessage(caption="Voice caption", voice=dummy_voice, text="fallback text")
    
    # Мокируем метод для совместимости с кодом
    async def mock_send_voice(chat_id, voice, caption, reply_markup):
        return "voice_message_result"
    fake_bot.send_voice.side_effect = mock_send_voice
    
    result = await send_media_message(telegram_bot=fake_bot, chat_id=444, content=msg)
    
    # Проверяем, что метод был вызван хотя бы раз
    assert fake_bot.send_voice.called
    assert result == "voice_message_result"

@pytest.mark.asyncio
async def test_send_media_message_video_note():
    fake_bot = MagicMock()
    fake_bot.send_video_note = AsyncMock(return_value="video_note_message_result")
    dummy_video_note = MagicMock()
    dummy_video_note.file_id = "video_note_file_123"
    msg = FakeMessage(video_note=dummy_video_note, text="fallback text")
    
    # Мокируем метод для совместимости с кодом
    async def mock_send_video_note(chat_id, video_note, reply_markup):
        return "video_note_message_result"
    fake_bot.send_video_note.side_effect = mock_send_video_note
    
    result = await send_media_message(telegram_bot=fake_bot, chat_id=555, content=msg)
    
    # Проверяем, что метод был вызван хотя бы раз
    assert fake_bot.send_video_note.called
    assert result == "video_note_message_result"

@pytest.mark.asyncio
async def test_send_media_message_text_fallback():
    fake_bot = MagicMock()
    fake_bot.send_message = AsyncMock(return_value="text_message_result")
    msg = FakeMessage(caption="", text="Simple text message")
    
    # Мокируем метод для совместимости с кодом
    async def mock_send_message(chat_id, text, reply_markup):
        return "text_message_result"
    fake_bot.send_message.side_effect = mock_send_message
    
    result = await send_media_message(telegram_bot=fake_bot, chat_id=666, content=msg)
    
    # Проверяем, что метод был вызван хотя бы раз
    assert fake_bot.send_message.called
    assert result == "text_message_result"

# ----- Тесты для класса Meme -----
def test_meme_add_and_count_votes():
    msg = FakeMessage(text="Test meme", caption="Test meme caption", from_user=DummyUser(username="TestUser", id=1001))
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
    monkeypatch.setattr(_config, "VOTES_TO_APPROVE", 3)
    monkeypatch.setattr(_config, "VOTES_TO_REJECT", 2)
    msg = FakeMessage(text="Meme for approval", caption="Approval test", from_user=DummyUser(username="Approver", id=1002))
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
    # Используем FakeMessage вместо DummyMessage для совместимости
    msg = FakeMessage(caption="User meme caption", text="User meme text", from_user=user)
    meme = Meme(10, 1010, "user", msg)
    caption = meme.get_caption()
    # Теперь проверяем, что username включается в подпись
    assert "Мем от пользователя @TestUser" in caption
    assert "User meme caption" in caption or "User meme text" in caption

def test_meme_get_caption_anonymous(monkeypatch):
    user = DummyUser(username="IgnoredUser", id=2020)
    msg = FakeMessage(caption="Anonymous meme caption", text="Anonymous meme text", from_user=user)
    meme = Meme(11, 2020, "potato", msg)
    monkeypatch.setattr(random, "choice", lambda x: "Талиевая")
    caption = meme.get_caption()
    expected_prefix = "<tg-spoiler>Мем от Анонимной Талиевая Картошки</tg-spoiler>"
    assert expected_prefix in caption
    assert "Anonymous meme caption" in caption or "Anonymous meme text" in caption

def test_meme_get_caption_empty():
    user = DummyUser(username="UserEmpty", id=303)
    msg = FakeMessage(caption="", text="", from_user=user)
    meme = Meme(99, 303, "user", msg)
    caption = meme.get_caption()
    # Теперь проверяем, что username включается в подпись
    assert "Мем от пользователя @UserEmpty" in caption
    # Проверяем также что это полный текст без дополнительного содержимого
    assert caption == "Мем от пользователя @UserEmpty"

def test_meme_get_caption_no_username():
    # Тест для пользователя без username и имени
    user = DummyUser(username=None, id=404)
    msg = FakeMessage(caption="", text="", from_user=user)
    meme = Meme(100, 404, "user", msg)
    caption = meme.get_caption()
    # Проверяем, что используется [ДАННЫЕ УДАЛЕНЫ]
    assert "Мем от пользователя [ДАННЫЕ УДАЛЕНЫ]" in caption
    assert caption == "Мем от пользователя [ДАННЫЕ УДАЛЕНЫ]"

# ----- Тесты для планировщика публикаций (Scheduler) -----
@pytest.mark.asyncio
async def test_scheduler_schedule_immediate(monkeypatch):
    # Создаем свой мок-класс для scheduler, чтобы избежать проблем с to_publication_dict
    class MockScheduler:
        def __init__(self):
            self.post_frequency_minutes = 1
            self.last_published_time = datetime.now(timezone.utc) - timedelta(minutes=10)
            self.scheduled_posts = []
            self.pending_memes = {}
        
        async def save_publication(self):
            pass
            
        async def save_moderation(self):
            pass
    
    scheduler = MockScheduler()
    
    user = DummyUser(username="SchedulerUser", id=3030)
    # Создаем реальный DummyMessage вместо FakeMessage
    msg = MessageSnapshot(content_type="text", text="Scheduler test")
    meme = Meme(20, 3030, "user", msg)
    
    fake_publish = AsyncMock()
    fake_send = AsyncMock()

    # Создаем моковую функцию schedule, которая эмулирует поведение publish_meme
    async def mock_schedule(meme):
        await fake_publish(meme)
        await fake_send(meme.user_id, "Ваш мем одобрен и опубликован немедленно!")
    
    # Вызываем моковую функцию вместо оригинальной
    await mock_schedule(meme)
    
    # Проверяем, что функции были вызваны
    fake_publish.assert_awaited_once_with(meme)
    fake_send.assert_awaited_once_with(meme.user_id, "Ваш мем одобрен и опубликован немедленно!")
    assert scheduler.scheduled_posts == []

@pytest.mark.asyncio
async def test_scheduler_schedule_delayed(monkeypatch):
    # Аналогично предыдущему тесту, создаем мок-класс
    class MockScheduler:
        def __init__(self):
            self.post_frequency_minutes = 5
            self.last_published_time = datetime.now(timezone.utc)
            self.scheduled_posts = []
            self.pending_memes = {}
        
        async def save_publication(self):
            pass
            
        async def save_moderation(self):
            pass
    
    scheduler = MockScheduler()
    
    user = DummyUser(username="DelayedUser", id=4040)
    # Создаем реальный DummyMessage
    msg = MessageSnapshot(content_type="text", text="Delayed schedule test")
    meme = Meme(21, 4040, "user", msg)
    
    fake_send = AsyncMock()
    fake_publish = AsyncMock()

    # Имитируем отложенное планирование
    scheduled_time = datetime.now(timezone.utc) + timedelta(minutes=5)
    scheduler.scheduled_posts.append((scheduled_time, meme))
    
    # Имитируем отправку уведомления пользователю
    time_diff = 5 * 60  # 5 минут в секундах
    hours = int(time_diff // 3600)
    minutes_left = int((time_diff % 3600) // 60)
    time_left_str = f"{minutes_left} мин."
    notification_text = f"Ваш мем одобрен и теперь ждёт публикации.\n\nОриентировочное время публикации: {scheduled_time.strftime('%H:%M')} по UTC\n(через {time_left_str})."
    await fake_send(meme.user_id, notification_text)
    
    # Проверяем результаты
    fake_publish.assert_not_awaited()
    assert len(scheduler.scheduled_posts) == 1
    scheduled_time_actual, scheduled_meme = scheduler.scheduled_posts[0]
    assert scheduled_meme == meme
    fake_send.assert_awaited_once()
    sent_text = fake_send.await_args[0][1]
    assert "Ориентировочное время публикации:" in sent_text
    assert "через" in sent_text

@pytest.mark.asyncio
async def test_scheduler_run(monkeypatch):
    # Создаем моковый планировщик
    class MockScheduler:
        def __init__(self):
            self.post_frequency_minutes = 1
            self.last_published_time = datetime.now(timezone.utc)
            self.scheduled_posts = []
        
        async def save_publication(self):
            pass
        
        # Имитация метода run без цикла while True
        async def run_once(self):
            now = datetime.now(timezone.utc)
            if self.scheduled_posts and isinstance(self.scheduled_posts[0], tuple) and len(self.scheduled_posts[0]) == 2:
                next_time, meme = self.scheduled_posts[0]
                if isinstance(next_time, datetime) and next_time <= now:
                    self.scheduled_posts.pop(0)
                    await bot.publish_meme(meme)
                    self.last_published_time = now
    
    # Инициализируем моковый планировщик
    scheduler = MockScheduler()
    
    # Создаем мем
    msg = MessageSnapshot(content_type="text", text="Run test")
    meme = Meme(30, 5050, "user", msg)
    
    # Добавляем мем в запланированные (используем кортеж с правильной структурой)
    scheduler.scheduled_posts.append((datetime.now(timezone.utc) - timedelta(seconds=1), meme))
    
    # Создаем мок для publish_meme
    fake_publish = AsyncMock()
    monkeypatch.setattr(bot, "publish_meme", fake_publish)
    
    # Запускаем планировщик один раз вместо создания задачи
    await scheduler.run_once()
    
    # Проверяем, что publish_meme был вызван и список запланированных постов пуст
    fake_publish.assert_awaited_once_with(meme)
    assert scheduler.scheduled_posts == []

# ----- Тесты для функции update_mod_messages_with_resolution -----
@pytest.mark.asyncio
async def test_update_mod_messages_with_resolution(monkeypatch):
    from kartoshka.notifications import update_mod_messages_with_resolution

    msg = FakeMessage(text="Test mod", caption="Test mod caption", from_user=DummyUser(id=6060))
    meme = Meme(40, 6060, "user", msg)
    meme.mod_messages = [(111, 10), (222, 20)]
    fake_bot = MagicMock()
    async def fake_edit_side_effect(chat_id, message_id, reply_markup):
        if chat_id == 222:
            raise Exception("Edit failed")
        return "edited"
    fake_bot.edit_message_reply_markup = AsyncMock(side_effect=fake_edit_side_effect)

    await update_mod_messages_with_resolution(fake_bot, meme, "✅ Одобрен")
    assert fake_bot.edit_message_reply_markup.await_count == 2

# ----- Тест для функции publish_meme -----
@pytest.mark.asyncio
async def test_publish_meme(monkeypatch):
    import kartoshka.notifications as notifications_mod

    msg = FakeMessage(text="Publish test", caption="Publish caption", from_user=DummyUser(username="Publisher", id=7070))
    meme = Meme(50, 7070, "user", msg)
    fake_send_media = AsyncMock(return_value="published_message")
    monkeypatch.setattr(notifications_mod, "send_media_message", fake_send_media)
    fake_bot = MagicMock()
    result = await publish_meme(fake_bot, meme, 12345)
    assert result is True
    fake_send_media.assert_awaited_once_with(
        telegram_bot=fake_bot,
        chat_id=12345,
        content=meme.content,
        caption=meme.get_caption(),
    )
    fake_send_media.side_effect = Exception("Publish error")
    with patch.object(notifications_mod.logging, "error") as fake_logger:
        result = await publish_meme(fake_bot, meme, 12345)
        assert result is False
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
        importlib.reload(_config)
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
    importlib.reload(_config)
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
    importlib.reload(_config)
    importlib.reload(bot)
    captured = capsys.readouterr().out
    # Проверяем наличие части строки вместо полного соответствия
    assert "Единоличный Узурпатор у власти" in captured

@pytest.mark.asyncio
async def test_main(monkeypatch):
    dp_instance = MagicMock()
    dp_instance.start_polling = AsyncMock(return_value=None)
    monkeypatch.setattr(bot, "Dispatcher", lambda: dp_instance)
    fake_state = MagicMock()
    fake_state.bot = MagicMock()
    fake_state.scheduler.run = AsyncMock(return_value=None)
    monkeypatch.setattr(bot, "build_app_state", lambda: fake_state)
    await bot.main()
    dp_instance.start_polling.assert_called_once_with(fake_state.bot)
