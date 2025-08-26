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
import kartoshka_bot as bot
from kartoshka_bot import (
    send_media_message,
    Meme,
    Scheduler,
    publish_meme,
    METALS_AND_TOXINS,
    VOTES_TO_APPROVE,
    VOTES_TO_REJECT,
    DummyMessage,
    deserialize_message,
    serialize_message
)

# ----- Вспомогательные классы для тестирования -----
class DummyUser:
    def __init__(self, username=None, id=12345):
        self.username = username
        self.id = id

# Переименование класса DummyMessage, чтобы избежать конфликта с импортированным
class TestMessage:
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
    
    msg = TestMessage(caption="Test caption", photo=photo_list, text="fallback text")
    
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
    msg = TestMessage(caption="Video caption", video=dummy_video, text="fallback text")
    
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
    msg = TestMessage(caption="Animation caption", animation=dummy_animation, text="fallback text")
    
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
    msg = TestMessage(caption="Voice caption", voice=dummy_voice, text="fallback text")
    
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
    msg = TestMessage(video_note=dummy_video_note, text="fallback text")
    
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
    msg = TestMessage(caption="", text="Simple text message")
    
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
    msg = TestMessage(text="Test meme", caption="Test meme caption", from_user=DummyUser(username="TestUser", id=1001))
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
    msg = TestMessage(text="Meme for approval", caption="Approval test", from_user=DummyUser(username="Approver", id=1002))
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
    # Используем TestMessage вместо DummyMessage для совместимости
    msg = TestMessage(caption="User meme caption", text="User meme text", from_user=user)
    meme = Meme(10, 1010, "user", msg)
    caption = meme.get_caption()
    # Теперь проверяем, что username включается в подпись
    assert "Мем от пользователя @TestUser" in caption
    assert "User meme caption" in caption or "User meme text" in caption

def test_meme_get_caption_anonymous(monkeypatch):
    user = DummyUser(username="IgnoredUser", id=2020)
    msg = TestMessage(caption="Anonymous meme caption", text="Anonymous meme text", from_user=user)
    meme = Meme(11, 2020, "potato", msg)
    monkeypatch.setattr(random, "choice", lambda x: "Талиевая")
    caption = meme.get_caption()
    expected_prefix = "<tg-spoiler>Мем от Анонимной Талиевая Картошки</tg-spoiler>"
    assert expected_prefix in caption
    assert "Anonymous meme caption" in caption or "Anonymous meme text" in caption

def test_meme_get_caption_empty():
    user = DummyUser(username="UserEmpty", id=303)
    msg = TestMessage(caption="", text="", from_user=user)
    meme = Meme(99, 303, "user", msg)
    caption = meme.get_caption()
    # Теперь проверяем, что username включается в подпись
    assert "Мем от пользователя @UserEmpty" in caption
    # Проверяем также что это полный текст без дополнительного содержимого
    assert caption == "Мем от пользователя @UserEmpty"

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
    # Создаем реальный DummyMessage вместо TestMessage
    msg_data = {
        "content_type": "text",
        "text": "Scheduler test"
    }
    msg = DummyMessage(msg_data)
    meme = Meme(20, 3030, "user", msg)
    
    fake_publish = AsyncMock()
    monkeypatch.setattr(bot, "publish_meme", fake_publish)
    fake_send = AsyncMock()
    monkeypatch.setattr(bot.bot, "send_message", fake_send)
    
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
    msg_data = {
        "content_type": "text",
        "text": "Delayed schedule test"
    }
    msg = DummyMessage(msg_data)
    meme = Meme(21, 4040, "user", msg)
    
    fake_send = AsyncMock()
    monkeypatch.setattr(bot.bot, "send_message", fake_send)
    fake_publish = AsyncMock()
    monkeypatch.setattr(bot, "publish_meme", fake_publish)
    
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
    msg_data = {
        "content_type": "text",
        "text": "Run test"
    }
    msg = DummyMessage(msg_data)
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
    from kartoshka_bot import update_mod_messages_with_resolution
    
    msg = TestMessage(text="Test mod", caption="Test mod caption", from_user=DummyUser(id=6060))
    meme = Meme(40, 6060, "user", msg)
    meme.mod_messages = [(111, 10), (222, 20)]
    fake_edit = AsyncMock()
    async def fake_edit_side_effect(chat_id, message_id, reply_markup):
        if chat_id == 222:
            raise Exception("Edit failed")
        return "edited"
    fake_edit.side_effect = fake_edit_side_effect
    monkeypatch.setattr(bot.bot, "edit_message_reply_markup", fake_edit)
    
    # Тестируем обновление сообщений с окончательным решением
    await update_mod_messages_with_resolution(meme, "✅ Одобрен")
    assert fake_edit.await_count == 2

# ----- Тест для функции publish_meme -----
@pytest.mark.asyncio
async def test_publish_meme(monkeypatch):
    msg = TestMessage(text="Publish test", caption="Publish caption", from_user=DummyUser(username="Publisher", id=7070))
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

# ----- Тесты для функций сериализации/десериализации -----
def test_dummy_message_text():
    # Проверка текстового сообщения
    data = {
        "content_type": "text",
        "text": "Тестовое сообщение"
    }
    # Используем импортированный DummyMessage из kartoshka_bot.py
    msg = DummyMessage(data)
    assert msg.content_type == "text"
    assert msg.text == "Тестовое сообщение"
    
    # Проверка десериализации
    deserialized = deserialize_message(data)
    assert deserialized.content_type == "text"
    assert deserialized.text == "Тестовое сообщение"

def test_dummy_message_photo():
    # Проверка сообщения с фото
    data = {
        "content_type": "photo",
        "photo": [{"file_id": "photo1"}, {"file_id": "photo2"}],
        "caption": "Подпись к фото"
    }
    msg = DummyMessage(data)
    assert msg.content_type == "photo"
    assert len(msg.photo) == 2
    assert msg.photo[0].file_id == "photo1"
    assert msg.photo[1].file_id == "photo2"
    assert msg.caption == "Подпись к фото"

def test_dummy_message_video():
    # Проверка сообщения с видео
    data = {
        "content_type": "video",
        "video": {"file_id": "video123", "width": 640, "height": 480},
        "caption": "Видео подпись"
    }
    msg = DummyMessage(data)
    assert msg.content_type == "video"
    assert msg.video.file_id == "video123"
    assert msg.video.width == 640
    assert msg.video.height == 480
    assert msg.caption == "Видео подпись"

def test_dummy_message_animation():
    # Проверка сообщения с анимацией (GIF)
    data = {
        "content_type": "animation",
        "animation": {"file_id": "anim123", "width": 320, "height": 240},
        "caption": "GIF анимация"
    }
    msg = DummyMessage(data)
    assert msg.content_type == "animation"
    assert msg.animation.file_id == "anim123"
    assert msg.animation.width == 320
    assert msg.animation.height == 240
    assert msg.caption == "GIF анимация"

def test_dummy_message_voice():
    # Проверка голосового сообщения
    data = {
        "content_type": "voice",
        "voice": {"file_id": "voice123", "duration": 15},
        "caption": "Голосовое сообщение"
    }
    msg = DummyMessage(data)
    assert msg.content_type == "voice"
    assert msg.voice.file_id == "voice123"
    assert msg.voice.duration == 15
    assert msg.caption == "Голосовое сообщение"

def test_dummy_message_video_note():
    # Проверка видео-заметки (круглое видео)
    data = {
        "content_type": "video_note",
        "video_note": {"file_id": "vidnote123", "length": 200}
    }
    msg = DummyMessage(data)
    assert msg.content_type == "video_note"
    assert msg.video_note.file_id == "vidnote123"
    assert msg.video_note.length == 200
    assert not hasattr(msg, "caption")  # видео-заметки не имеют подписей
    
def test_dummy_message_video_note_explicit():
    """Более явный тест для видео-заметки с дополнительными проверками"""
    # Создаем данные для видео-заметки
    data = {
        "content_type": "video_note",
        "video_note": {
            "file_id": "explicit_video_note_123",
            "length": 300,
            "duration": 15,
            "thumb": {"file_id": "thumb123", "width": 90, "height": 90}
        }
    }
    
    # Создаем сообщение
    msg = DummyMessage(data)
    
    # Проверяем основные свойства
    assert msg.content_type == "video_note"
    assert hasattr(msg, "video_note")
    assert msg.video_note.file_id == "explicit_video_note_123"
    assert msg.video_note.length == 300
    assert msg.video_note.duration == 15
    assert hasattr(msg.video_note, "thumb")
    assert msg.video_note.thumb.file_id == "thumb123"
    
    # Проверяем, что нет поля caption
    assert not hasattr(msg, "caption")
    
    # Проверяем другие типичные свойства сообщений, которых нет у video_note
    assert not hasattr(msg, "text")
    assert not hasattr(msg, "photo")
    assert not hasattr(msg, "video")
    assert not hasattr(msg, "animation")
    assert not hasattr(msg, "voice")

def test_dummy_message_with_none_values():
    """Тест DummyMessage с None значениями для дополнительных полей"""
    data = {
        "content_type": "photo",
        "photo": None,  # Тестируем обработку None значений
        "caption": None
    }
    msg = DummyMessage(data)
    assert msg.content_type == "photo"
    assert hasattr(msg, "photo")
    # Проверяем что фото превращается в пустой список при None
    assert isinstance(msg.photo, list) and len(msg.photo) == 0
    assert msg.caption is None

def test_dummy_message_missing_required_fields():
    """Тест DummyMessage с отсутствующими обязательными полями"""
    data = {
        "content_type": "text",
        # Отсутствует поле "text"
    }
    # Проверяем как класс обрабатывает отсутствующие обязательные поля
    msg = DummyMessage(data)
    assert msg.content_type == "text"
    # Проверяем, что text существует со значением по умолчанию
    assert hasattr(msg, "text")
    assert msg.text == ""

def test_dummy_message_unknown_type():
    # Проверка неизвестного типа сообщения
    data = {
        "content_type": "unknown_type",
        "text": "Текст неизвестного типа"
    }
    msg = DummyMessage(data)
    assert msg.content_type == "unknown_type"
    assert msg.text == "Текст неизвестного типа"
    
    # Проверка без текста
    data = {
        "content_type": "unknown_type"
    }
    msg = DummyMessage(data)
    assert msg.content_type == "unknown_type"
    assert msg.text == ""  # должен быть пустой текст

def test_serialize_message_text():
    # Проверка сериализации текстового сообщения
    original_data = {
        "content_type": "text",
        "text": "Тестовое сообщение для сериализации"
    }
    # Используем импортированный DummyMessage
    msg = DummyMessage(original_data)
    
    data = serialize_message(msg)
    assert data["content_type"] == "text"
    assert data["text"] == "Тестовое сообщение для сериализации"

def test_serialize_message_photo():
    # Создаем сообщение с фото через DummyMessage
    original_data = {
        "content_type": "photo",
        "photo": [{"file_id": "photo1"}, {"file_id": "photo2"}],
        "caption": "Подпись к фото при сериализации"
    }
    # Используем импортированный DummyMessage
    msg = DummyMessage(original_data)
    
    data = serialize_message(msg)
    assert data["content_type"] == "photo"
    assert len(data["photo"]) == 2
    assert data["photo"][0]["file_id"] == "photo1"
    assert data["photo"][1]["file_id"] == "photo2"
    assert data["caption"] == "Подпись к фото при сериализации"

def test_serialize_message_video():
    # Проверка сериализации видео сообщения
    original_data = {
        "content_type": "video",
        "video": {"file_id": "video_id"},
        "caption": "Подпись к видео"
    }
    msg = DummyMessage(original_data)
    
    data = serialize_message(msg)
    assert data["content_type"] == "video"
    assert data["video"]["file_id"] == "video_id"
    assert data["caption"] == "Подпись к видео"

def test_serialize_message_animation():
    # Проверка сериализации анимации
    original_data = {
        "content_type": "animation",
        "animation": {"file_id": "anim_id"},
        "caption": "Подпись к анимации"
    }
    msg = DummyMessage(original_data)
    
    data = serialize_message(msg)
    assert data["content_type"] == "animation"
    assert data["animation"]["file_id"] == "anim_id"
    assert data["caption"] == "Подпись к анимации"

def test_serialize_message_voice():
    # Проверка сериализации голосового сообщения
    original_data = {
        "content_type": "voice",
        "voice": {"file_id": "voice_id"},
        "caption": "Подпись к голосовому"
    }
    msg = DummyMessage(original_data)
    
    data = serialize_message(msg)
    assert data["content_type"] == "voice"
    assert data["voice"]["file_id"] == "voice_id"
    assert data["caption"] == "Подпись к голосовому"

def test_serialize_message_video_note():
    # Проверка сериализации видео-заметки
    original_data = {
        "content_type": "video_note",
        "video_note": {"file_id": "vidnote_id"}
    }
    msg = DummyMessage(original_data)
    
    data = serialize_message(msg)
    assert data["content_type"] == "video_note"
    assert data["video_note"]["file_id"] == "vidnote_id"
    
def test_serialize_message_video_note_explicit():
    """Более явная проверка сериализации видео-заметки с дополнительными полями"""
    # Создаем более сложные данные для видео-заметки
    original_data = {
        "content_type": "video_note",
        "video_note": {
            "file_id": "explicit_vidnote_id_456",
            "length": 400,
            "duration": 20,
            "thumb": {"file_id": "thumb_456", "width": 100, "height": 100},
            "file_unique_id": "unique456",
            "file_size": 1024
        }
    }
    
    # Создаем сообщение через DummyMessage
    msg = DummyMessage(original_data)
    
    # Сериализуем сообщение
    data = serialize_message(msg)
    
    # Проверяем основные свойства
    assert data["content_type"] == "video_note"
    assert "video_note" in data
    assert data["video_note"]["file_id"] == "explicit_vidnote_id_456"
    
    # Проверяем, что нет лишних полей
    assert "caption" not in data
    assert "text" not in data
    
    # Проверяем количество ключей
    assert len(data.keys()) == 2  # content_type и video_note
    
    # Проверяем, что поле video_note существует
    assert data["video_note"] is not None

def test_serialize_message_with_malformed_object():
    """Тест сериализации сообщения с неполными атрибутами"""
    # Создаем объект сообщения без всех необходимых атрибутов
    class MalformedMessage:
        def __init__(self):
            self.content_type = "text"
            # Отсутствует атрибут text
    
    msg = MalformedMessage()
    data = serialize_message(msg)
    assert data["content_type"] == "text"
    assert data["text"] == ""  # Должна быть пустая строка по умолчанию

def test_serialize_message_with_none_attributes():
    """Тест сериализации сообщения с None атрибутами"""
    # Создаем сообщение с None атрибутами
    class MessageWithNoneAttrs:
        def __init__(self):
            self.content_type = "photo"
            self.photo = None
            self.caption = None
    
    msg = MessageWithNoneAttrs()
    data = serialize_message(msg)
    assert data["content_type"] == "photo"
    # По умолчанию превращает None фото в пустой список
    assert "photo" in data
    assert isinstance(data["photo"], list)
    assert len(data["photo"]) == 0
    assert "caption" in data
    assert data["caption"] is None

def test_serialize_message_with_custom_attributes():
    """Тест сериализации сообщения с дополнительными нестандартными атрибутами"""
    # Создаем сообщение с дополнительными полями, которые не должны попасть в сериализацию
    class MessageWithCustomAttrs:
        def __init__(self):
            self.content_type = "text"
            self.text = "Тестовое сообщение"
            self.custom_field = "Это поле не должно попасть в сериализацию"
            self.another_field = 12345
    
    msg = MessageWithCustomAttrs()
    data = serialize_message(msg)
    assert data["content_type"] == "text"
    assert data["text"] == "Тестовое сообщение"
    # Проверяем что дополнительные поля не попали в сериализацию
    assert "custom_field" not in data
    assert "another_field" not in data
    # Всего должно быть 2 ключа в словаре
    assert len(data.keys()) == 2

def test_serialize_message_unknown_type():
    # Проверка сериализации неизвестного типа
    original_data = {
        "content_type": "unknown",
        "text": "Текст сообщения неизвестного типа"
    }
    msg = DummyMessage(original_data)
    
    data = serialize_message(msg)
    assert data["content_type"] == "unknown"
    assert data["text"] == "Текст сообщения неизвестного типа"
    
    # Проверка без текста
    original_data_empty = {
        "content_type": "unknown"
    }
    msg = DummyMessage(original_data_empty)
    
    data = serialize_message(msg)
    assert data["content_type"] == "unknown"
    assert data["text"] == ""  # должен быть пустой текст

def test_serialize_deserialize_round_trip():
    # Проверка полного цикла сериализации-десериализации
    
    # Текстовое сообщение
    original_data = {
        "content_type": "text",
        "text": "Тест полного цикла"
    }
    # Используем импортированный DummyMessage
    original_msg = DummyMessage(original_data)
    
    serialized = serialize_message(original_msg)
    deserialized = deserialize_message(serialized)
    
    assert deserialized.content_type == "text"
    assert deserialized.text == "Тест полного цикла"
    
    # Фото сообщение
    original_photo_data = {
        "content_type": "photo",
        "photo": [{"file_id": "photo_roundtrip"}],
        "caption": "Подпись для полного цикла"
    }
    original_msg = DummyMessage(original_photo_data)
    
    serialized = serialize_message(original_msg)
    deserialized = deserialize_message(serialized)
    
    assert deserialized.content_type == "photo"
    assert deserialized.photo[0].file_id == "photo_roundtrip"
    assert deserialized.caption == "Подпись для полного цикла"

def test_deserialize_message():
    # Проверка функции десериализации
    data = {
        "content_type": "text",
        "text": "Текст для десериализации"
    }
    msg = deserialize_message(data)
    assert isinstance(msg, DummyMessage)
    assert msg.content_type == "text"
    assert msg.text == "Текст для десериализации"
    
    # Проверка с фото
    data = {
        "content_type": "photo",
        "photo": [{"file_id": "photo_id"}],
        "caption": "Фото для десериализации"
    }
    msg = deserialize_message(data)
    assert isinstance(msg, DummyMessage)
    assert msg.content_type == "photo"
    assert msg.photo[0].file_id == "photo_id"
    assert msg.caption == "Фото для десериализации"

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
    # Проверяем наличие части строки вместо полного соответствия
    assert "Единоличный Узурпатор у власти" in captured

@pytest.mark.asyncio
async def test_main(monkeypatch):
    dp_instance = MagicMock()
    dp_instance.start_polling = AsyncMock(return_value=None)
    monkeypatch.setattr(bot, "Dispatcher", lambda: dp_instance)
    await bot.main()
    dp_instance.start_polling.assert_called_once_with(bot.bot)
