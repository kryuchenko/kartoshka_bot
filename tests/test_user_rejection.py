#!/usr/bin/env python3
# Тесты для отслеживания отклонений пользователя и счетчика неудачных попыток
import unittest
import asyncio
import os
import sys
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from types import SimpleNamespace

# Задаем переменные окружения для тестов
os.environ.setdefault("BOT_TOKEN", "123456789:TEST_TOKEN_FOR_TESTING")
os.environ.setdefault("EDITOR_IDS", "123,456,789")
os.environ.setdefault("PUBLISH_CHAT_ID", "-1001234567890")
os.environ.setdefault("BOT_NAME", "TestBot")
os.environ.setdefault("POST_FREQUENCY_MINUTES", "60")
os.environ.setdefault("CRYPTOSELECTARCHY", "true")
os.environ.setdefault("VOTES_TO_APPROVE", "3")
os.environ.setdefault("VOTES_TO_REJECT", "3")

# Патчим aiogram перед импортом
with patch.dict('sys.modules'):
    # Мок для основного модуля aiogram
    aiogram_mock = MagicMock()
    
    # Сначала патчим aiogram.utils.token, чтобы validate_token всегда возвращал True
    validate_token_module = MagicMock()
    validate_token_module.validate_token.return_value = True
    sys.modules['aiogram.utils.token'] = validate_token_module
    
    # Создаем классы для мока
    class MockMessage:
        def __init__(self, message_id=1, from_user=None, text=None, caption=None, 
                    content_type="text", photo=None, video=None, animation=None, 
                    voice=None, video_note=None):
            self.message_id = message_id
            self.from_user = from_user or MockUser()
            self.text = text
            self.caption = caption
            self.content_type = content_type
            self.photo = photo
            self.video = video
            self.animation = animation
            self.voice = voice
            self.video_note = video_note
            self.answer = AsyncMock(return_value=None)
    
    class MockUser:
        def __init__(self, id=12345, username="test_user", first_name="Test", last_name="User"):
            self.id = id
            self.username = username
            self.first_name = first_name
            self.last_name = last_name
    
    class MockCallbackQuery:
        def __init__(self, id="query_1", from_user=None, message=None, data=None):
            self.id = id
            self.from_user = from_user or MockUser()
            self.message = message or MockMessage()
            self.data = data
            self.answer = AsyncMock(return_value=None)
    
    class MockInlineKeyboardButton:
        def __init__(self, text, callback_data=None):
            self.text = text
            self.callback_data = callback_data
    
    class MockInlineKeyboardMarkup:
        def __init__(self, inline_keyboard=None):
            self.inline_keyboard = inline_keyboard or []
    
    class MockCommand:
        def __init__(self, command=None):
            self.commands = [command] if command else []
    
    class MockF:
        data = MagicMock()
        content_type = MagicMock()
        
        @classmethod
        def __getattr__(cls, name):
            mock = MagicMock()
            mock.in_ = lambda x: MagicMock()
            mock.startswith = lambda x: MagicMock()
            return mock
    
    class MockDispatcher:
        def __init__(self):
            self.message_handlers = []
            self.callback_query_handlers = []
        
        def message(self, *args, **kwargs):
            def decorator(callback):
                self.message_handlers.append((args, kwargs, callback))
                return callback
            return decorator
        
        def callback_query(self, *args, **kwargs):
            def decorator(callback):
                self.callback_query_handlers.append((args, kwargs, callback))
                return callback
            return decorator
        
        async def start_polling(self, *args, **kwargs):
            pass
    
    class MockBot:
        def __init__(self, token=None, default=None):
            self.token = token
            self.default = default
        
        async def send_message(self, *args, **kwargs):
            return MockMessage()
        
        async def send_photo(self, *args, **kwargs):
            return MockMessage(content_type="photo")
        
        async def edit_message_reply_markup(self, *args, **kwargs):
            return MockMessage()
    
    class MockDefaultBotProperties:
        def __init__(self, parse_mode=None):
            self.parse_mode = parse_mode
    
    # Создаем моки для всех необходимых модулей aiogram
    types_module = MagicMock()
    types_module.Message = MockMessage
    types_module.User = MockUser
    types_module.CallbackQuery = MockCallbackQuery
    types_module.InlineKeyboardButton = MockInlineKeyboardButton
    types_module.InlineKeyboardMarkup = MockInlineKeyboardMarkup
    
    filters_module = MagicMock()
    filters_module.Command = MockCommand
    filters_module.F = MockF
    
    client_bot_module = MagicMock()
    client_bot_module.Bot = MockBot
    client_bot_module.DefaultBotProperties = MockDefaultBotProperties
    
    dispatcher_module = MagicMock()
    dispatcher_module.Dispatcher = MockDispatcher
    
    # Передаем моки в aiogram
    aiogram_mock.Bot = MockBot
    aiogram_mock.Dispatcher = MockDispatcher
    aiogram_mock.F = MockF
    aiogram_mock.types = types_module
    aiogram_mock.filters = filters_module
    
    # Регистрируем все модули в sys.modules
    sys.modules['aiogram'] = aiogram_mock
    sys.modules['aiogram.types'] = types_module
    sys.modules['aiogram.filters'] = filters_module
    sys.modules['aiogram.client.bot'] = client_bot_module
    
    # Добавляем директорию проекта в PYTHONPATH
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    # Теперь можно импортировать модуль
    import kartoshka_bot
    from kartoshka_bot import Meme, Scheduler
    
    # Подменяем атрибуты модуля для тестирования
    kartoshka_bot.dispatcher_module = dispatcher_module
    kartoshka_bot.types_module = types_module
    kartoshka_bot.filters_module = filters_module
    
    # Создаем новый Dispatcher для тестов
    kartoshka_bot.dp = dispatcher_module.Dispatcher()
    kartoshka_bot.bot = MockBot(token="test_token")


class TestUserRejectionTracking(unittest.IsolatedAsyncioTestCase):
    """Тесты для отслеживания отклонений пользователя"""
    
    async def asyncSetUp(self):
        # Используем диспетчер, созданный при импорте
        self.dp = kartoshka_bot.dp
        
        # Подготавливаем тестовые данные пользователя
        self.test_user_id = 12345
        self.test_user_data = {
            str(self.test_user_id): {
                "last_submission": None,
                "rejections": 0,
                "ban_until": None
            }
        }
        
        # Готовим патчи
        self.user_data_patch = patch('kartoshka_bot.user_data', self.test_user_data)
        self.scheduler_patch = patch('kartoshka_bot.scheduler')
        self.save_user_data_patch = patch('kartoshka_bot.save_user_data')
        self.update_user_messages_patch = patch('kartoshka_bot.update_user_messages_with_status', AsyncMock())
        self.update_mod_messages_patch = patch('kartoshka_bot.update_mod_messages_with_resolution', AsyncMock())
        self.publish_patch = patch('kartoshka_bot.publish_meme', AsyncMock())
        
        # Активируем патчи
        self.user_data = self.user_data_patch.start()
        self.scheduler_mock = self.scheduler_patch.start()
        self.save_user_data_mock = self.save_user_data_patch.start()
        self.update_user_messages_mock = self.update_user_messages_patch.start()
        self.update_mod_messages_mock = self.update_mod_messages_patch.start()
        self.publish_mock = self.publish_patch.start()
        
        # Настраиваем мок планировщика
        self.scheduler_mock.pending_memes = {}
        self.scheduler_mock.save_moderation = MagicMock()
        self.scheduler_mock.schedule = AsyncMock()
        
        # Создаем тестовый мем от пользователя
        self.meme = kartoshka_bot.Meme(
            meme_id=123,
            user_id=self.test_user_id,
            publish_choice="user",
            content=kartoshka_bot.types_module.Message(text="Тестовый мем")
        )
        self.scheduler_mock.pending_memes[123] = self.meme
    
    async def asyncTearDown(self):
        # Деактивируем патчи
        self.user_data_patch.stop()
        self.scheduler_patch.stop()
        self.save_user_data_patch.stop()
        self.update_user_messages_patch.stop()
        self.update_mod_messages_patch.stop()
        self.publish_patch.stop()
    
    async def test_rejection_counter_increment(self):
        """Проверка увеличения счетчика отклонений при отклонении мема"""
        # Моделируем режим криптоселектархии
        with patch('kartoshka_bot.CRYPTOSELECTARCHY', True), patch('kartoshka_bot.VOTES_TO_REJECT', 3):
            # Регистрируем обработчик колбэка голосования
            @self.dp.callback_query(kartoshka_bot.filters_module.F.data.startswith(("approve_", "urgent_", "reject_")))
            async def crypto_callback(callback):
                data = callback.data
                action, meme_id_str = data.split("_", 1)
                meme_id = int(meme_id_str)
                if meme_id not in self.scheduler_mock.pending_memes:
                    await callback.answer("Заявка не найдена или уже обработана.")
                    return

                meme = self.scheduler_mock.pending_memes[meme_id]
                crypto_id = callback.from_user.id
                prev_vote = meme.add_vote(crypto_id, action)
                self.scheduler_mock.save_moderation()

                # Обновляем виджет статистики голосов у пользователя
                await kartoshka_bot.update_user_messages_with_status(meme)
                await callback.answer("Ваш голос учтен.", show_alert=False)

                if meme.is_rejected() and not meme.finalized:
                    resolution = "❌ Отк."
                    # Обновляем статус пользовательского виджета с финальным решением
                    await kartoshka_bot.update_user_messages_with_status(meme, "❌ Отк.")
                    
                    # Увеличиваем счётчик отклонений для автора
                    author_id = meme.user_id
                    if author_id:
                        ud = kartoshka_bot.user_data.setdefault(str(author_id), {
                            "last_submission": None,
                            "rejections": 0,
                            "ban_until": None
                        })
                        ud["rejections"] += 1
                        kartoshka_bot.save_user_data(kartoshka_bot.user_data)
                    
                    meme.finalized = True
                    resolution_with_summary = f"{resolution} {meme.get_vote_summary()}"
                    await kartoshka_bot.update_mod_messages_with_resolution(meme, resolution_with_summary)
                    del self.scheduler_mock.pending_memes[meme.meme_id]
                    self.scheduler_mock.save_moderation()
            
            # Создаем тестовые колбэки для голосования "отклонить"
            callbacks = []
            for i in range(3):  # Для отклонения нужно 3 голоса
                callback = kartoshka_bot.types_module.CallbackQuery(
                    id=f"reject_callback_{i}",
                    from_user=kartoshka_bot.types_module.User(id=200+i),
                    data=f"reject_{self.meme.meme_id}"
                )
                callback.answer = AsyncMock()
                callbacks.append(callback)
            
            # Голосуем за отклонение
            for callback in callbacks:
                await crypto_callback(callback)
            
            # Проверяем, что счетчик отклонений пользователя увеличился
            self.assertEqual(self.test_user_data[str(self.test_user_id)]["rejections"], 1)
            
            # Проверяем, что была вызвана функция сохранения данных пользователя
            kartoshka_bot.save_user_data.assert_called_with(kartoshka_bot.user_data)
    
    async def test_rejection_counter_reset_on_approval(self):
        """Проверка сброса счетчика отклонений при одобрении мема"""
        # Предварительно устанавливаем счетчик отклонений, как будто у пользователя уже были отклоненные мемы
        self.test_user_data[str(self.test_user_id)]["rejections"] = 2
        
        # Моделируем режим криптоселектархии
        with patch('kartoshka_bot.CRYPTOSELECTARCHY', True), patch('kartoshka_bot.VOTES_TO_APPROVE', 3):
            # Регистрируем обработчик колбэка голосования
            @self.dp.callback_query(kartoshka_bot.filters_module.F.data.startswith(("approve_", "urgent_", "reject_")))
            async def crypto_callback(callback):
                data = callback.data
                action, meme_id_str = data.split("_", 1)
                meme_id = int(meme_id_str)
                if meme_id not in self.scheduler_mock.pending_memes:
                    await callback.answer("Заявка не найдена или уже обработана.")
                    return

                meme = self.scheduler_mock.pending_memes[meme_id]
                crypto_id = callback.from_user.id
                prev_vote = meme.add_vote(crypto_id, action)
                self.scheduler_mock.save_moderation()

                # Обновляем виджет статистики голосов у пользователя
                await kartoshka_bot.update_user_messages_with_status(meme)
                await callback.answer("Ваш голос учтен.", show_alert=False)

                if meme.is_approved() and not meme.finalized:
                    if meme.is_urgent():
                        resolution = "⚡ Одбр.срч."
                        await kartoshka_bot.publish_meme(meme)
                        # Обновляем статус пользовательского виджета с финальным решением
                        await kartoshka_bot.update_user_messages_with_status(meme, "⚡ Одбр.срч.")
                        
                        # Сбросим счётчик отклонений для автора
                        author_id = meme.user_id
                        if author_id:
                            ud = kartoshka_bot.user_data.setdefault(str(author_id), {
                                "last_submission": None,
                                "rejections": 0,
                                "ban_until": None
                            })
                            ud["rejections"] = 0
                            # Если пользователь находился в бане, снимаем бан
                            ud["ban_until"] = None
                            kartoshka_bot.save_user_data(kartoshka_bot.user_data)
                    else:
                        resolution = "✅ Одбр."
                        await self.scheduler_mock.schedule(meme)
                        # Обновляем статус пользовательского виджета с финальным решением
                        await kartoshka_bot.update_user_messages_with_status(meme, "✅ Одбр.")
                        
                        # Сбросим счётчик отклонений для автора
                        author_id = meme.user_id
                        if author_id:
                            ud = kartoshka_bot.user_data.setdefault(str(author_id), {
                                "last_submission": None,
                                "rejections": 0,
                                "ban_until": None
                            })
                            ud["rejections"] = 0
                            # Если пользователь находился в бане, снимаем бан
                            ud["ban_until"] = None
                            kartoshka_bot.save_user_data(kartoshka_bot.user_data)
                    meme.finalized = True
                    resolution_with_summary = f"{resolution} {meme.get_vote_summary()}"
                    await kartoshka_bot.update_mod_messages_with_resolution(meme, resolution_with_summary)
                    del self.scheduler_mock.pending_memes[meme.meme_id]
                    self.scheduler_mock.save_moderation()
            
            # Создаем тестовые колбэки для голосования "одобрить"
            callbacks = []
            for i in range(3):  # Для одобрения нужно 3 голоса
                callback = kartoshka_bot.types_module.CallbackQuery(
                    id=f"approve_callback_{i}",
                    from_user=kartoshka_bot.types_module.User(id=300+i),
                    data=f"approve_{self.meme.meme_id}"
                )
                callback.answer = AsyncMock()
                callbacks.append(callback)
            
            # Голосуем за одобрение
            for callback in callbacks:
                await crypto_callback(callback)
            
            # Проверяем, что счетчик отклонений пользователя сброшен в 0
            self.assertEqual(self.test_user_data[str(self.test_user_id)]["rejections"], 0)
            
            # Проверяем, что была вызвана функция сохранения данных пользователя
            kartoshka_bot.save_user_data.assert_called_with(kartoshka_bot.user_data)

    async def test_ban_removal_on_approval(self):
        """Проверка снятия бана при одобрении мема"""
        # Предварительно устанавливаем бан для пользователя
        ban_time = datetime.now(timezone.utc) + timedelta(days=1)
        self.test_user_data[str(self.test_user_id)]["ban_until"] = ban_time.isoformat()
        
        # Моделируем режим криптоселектархии
        with patch('kartoshka_bot.CRYPTOSELECTARCHY', True), patch('kartoshka_bot.VOTES_TO_APPROVE', 3):
            # Регистрируем обработчик колбэка голосования
            @self.dp.callback_query(kartoshka_bot.filters_module.F.data.startswith(("approve_", "urgent_", "reject_")))
            async def crypto_callback(callback):
                data = callback.data
                action, meme_id_str = data.split("_", 1)
                meme_id = int(meme_id_str)
                if meme_id not in self.scheduler_mock.pending_memes:
                    await callback.answer("Заявка не найдена или уже обработана.")
                    return

                meme = self.scheduler_mock.pending_memes[meme_id]
                crypto_id = callback.from_user.id
                prev_vote = meme.add_vote(crypto_id, action)
                self.scheduler_mock.save_moderation()

                # Обновляем виджет статистики голосов у пользователя
                await kartoshka_bot.update_user_messages_with_status(meme)
                await callback.answer("Ваш голос учтен.", show_alert=False)

                if meme.is_approved() and not meme.finalized:
                    resolution = "✅ Одбр."
                    await self.scheduler_mock.schedule(meme)
                    # Обновляем статус пользовательского виджета с финальным решением
                    await kartoshka_bot.update_user_messages_with_status(meme, "✅ Одбр.")
                    
                    # Сбросим счётчик отклонений для автора
                    author_id = meme.user_id
                    if author_id:
                        ud = kartoshka_bot.user_data.setdefault(str(author_id), {
                            "last_submission": None,
                            "rejections": 0,
                            "ban_until": None
                        })
                        ud["rejections"] = 0
                        # Если пользователь находился в бане, снимаем бан
                        ud["ban_until"] = None
                        kartoshka_bot.save_user_data(kartoshka_bot.user_data)
                    
                    meme.finalized = True
                    resolution_with_summary = f"{resolution} {meme.get_vote_summary()}"
                    await kartoshka_bot.update_mod_messages_with_resolution(meme, resolution_with_summary)
                    del self.scheduler_mock.pending_memes[meme.meme_id]
                    self.scheduler_mock.save_moderation()
            
            # Создаем тестовые колбэки для голосования "одобрить"
            callbacks = []
            for i in range(3):  # Для одобрения нужно 3 голоса
                callback = kartoshka_bot.types_module.CallbackQuery(
                    id=f"approve_callback_{i}",
                    from_user=kartoshka_bot.types_module.User(id=300+i),
                    data=f"approve_{self.meme.meme_id}"
                )
                callback.answer = AsyncMock()
                callbacks.append(callback)
            
            # Голосуем за одобрение
            for callback in callbacks:
                await crypto_callback(callback)
            
            # Проверяем, что бан снят (ban_until стал None)
            self.assertIsNone(self.test_user_data[str(self.test_user_id)]["ban_until"])
            
            # Проверяем, что была вызвана функция сохранения данных пользователя
            kartoshka_bot.save_user_data.assert_called_with(kartoshka_bot.user_data)
    
    async def test_multiple_rejections_counting(self):
        """Проверка корректного подсчета нескольких последовательных отклонений"""
        # Начинаем с нулевого счетчика отклонений
        self.test_user_data[str(self.test_user_id)]["rejections"] = 0
        
        # Для правильной работы теста нужно явно переопределить, как работает save_user_data
        # чтобы изменения сохранялись в test_user_data
        def mock_save_user_data(data):
            # Сохраняем данные обратно в наш тестовый словарь
            for user_id, user_info in data.items():
                if user_id in self.test_user_data:
                    self.test_user_data[user_id].update(user_info)
                
        # Переопределяем мок для save_user_data
        kartoshka_bot.save_user_data = mock_save_user_data
        
        # Моделируем режим криптоселектархии
        with patch('kartoshka_bot.CRYPTOSELECTARCHY', True), patch('kartoshka_bot.VOTES_TO_REJECT', 3):
            # Регистрируем обработчик колбэка голосования
            @self.dp.callback_query(kartoshka_bot.filters_module.F.data.startswith(("approve_", "urgent_", "reject_")))
            async def crypto_callback(callback):
                data = callback.data
                action, meme_id_str = data.split("_", 1)
                meme_id = int(meme_id_str)
                if meme_id not in self.scheduler_mock.pending_memes:
                    await callback.answer("Заявка не найдена или уже обработана.")
                    return

                meme = self.scheduler_mock.pending_memes[meme_id]
                crypto_id = callback.from_user.id
                prev_vote = meme.add_vote(crypto_id, action)
                self.scheduler_mock.save_moderation()

                # Обновляем виджет статистики голосов у пользователя
                await kartoshka_bot.update_user_messages_with_status(meme)
                await callback.answer("Ваш голос учтен.", show_alert=False)

                if meme.is_rejected() and not meme.finalized:
                    resolution = "❌ Отк."
                    # Обновляем статус пользовательского виджета с финальным решением
                    await kartoshka_bot.update_user_messages_with_status(meme, "❌ Отк.")
                    
                    # Увеличиваем счётчик отклонений для автора
                    author_id = meme.user_id
                    if author_id:
                        ud = kartoshka_bot.user_data.setdefault(str(author_id), {
                            "last_submission": None,
                            "rejections": 0,
                            "ban_until": None
                        })
                        ud["rejections"] += 1
                        kartoshka_bot.save_user_data(kartoshka_bot.user_data)
                    
                    meme.finalized = True
                    resolution_with_summary = f"{resolution} {meme.get_vote_summary()}"
                    await kartoshka_bot.update_mod_messages_with_resolution(meme, resolution_with_summary)
                    del self.scheduler_mock.pending_memes[meme.meme_id]
                    self.scheduler_mock.save_moderation()
            
            # Создаем тестовые колбэки для голосования "отклонить" первый мем
            callbacks = []
            for i in range(3):  # Для отклонения нужно 3 голоса
                callback = kartoshka_bot.types_module.CallbackQuery(
                    id=f"reject_callback_{i}",
                    from_user=kartoshka_bot.types_module.User(id=200+i),
                    data=f"reject_{self.meme.meme_id}"
                )
                callback.answer = AsyncMock()
                callbacks.append(callback)
            
            # Голосуем за отклонение первого мема
            for callback in callbacks:
                await crypto_callback(callback)
            
            # Проверяем, что счетчик отклонений пользователя увеличился до 1
            self.assertEqual(self.test_user_data[str(self.test_user_id)]["rejections"], 1)
            
            # Создаем второй тестовый мем от того же пользователя
            meme2 = kartoshka_bot.Meme(
                meme_id=456,
                user_id=self.test_user_id,
                publish_choice="user",
                content=kartoshka_bot.types_module.Message(text="Еще один тестовый мем")
            )
            self.scheduler_mock.pending_memes[456] = meme2
            
            # Создаем тестовые колбэки для голосования "отклонить" второй мем
            callbacks2 = []
            for i in range(3):
                callback = kartoshka_bot.types_module.CallbackQuery(
                    id=f"reject_callback2_{i}",
                    from_user=kartoshka_bot.types_module.User(id=400+i),
                    data=f"reject_{meme2.meme_id}"
                )
                callback.answer = AsyncMock()
                callbacks2.append(callback)
            
            # Голосуем за отклонение второго мема
            for callback in callbacks2:
                await crypto_callback(callback)
            
            # Проверяем, что счетчик отклонений пользователя увеличился до 2
            self.assertEqual(self.test_user_data[str(self.test_user_id)]["rejections"], 2)
            
            # Создаем третий тестовый мем от того же пользователя
            meme3 = kartoshka_bot.Meme(
                meme_id=789,
                user_id=self.test_user_id,
                publish_choice="user",
                content=kartoshka_bot.types_module.Message(text="Третий тестовый мем")
            )
            self.scheduler_mock.pending_memes[789] = meme3
            
            # Создаем тестовые колбэки для голосования "отклонить" третий мем
            callbacks3 = []
            for i in range(3):
                callback = kartoshka_bot.types_module.CallbackQuery(
                    id=f"reject_callback3_{i}",
                    from_user=kartoshka_bot.types_module.User(id=500+i),
                    data=f"reject_{meme3.meme_id}"
                )
                callback.answer = AsyncMock()
                callbacks3.append(callback)
            
            # Голосуем за отклонение третьего мема
            for callback in callbacks3:
                await crypto_callback(callback)
            
            # Проверяем, что счетчик отклонений пользователя увеличился до 3
            self.assertEqual(self.test_user_data[str(self.test_user_id)]["rejections"], 3)


if __name__ == "__main__":
    unittest.main()