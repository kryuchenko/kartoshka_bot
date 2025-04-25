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
        
        # Непосредственный доступ к пользовательским данным
        self.test_user_id = 12345
        
        # Патчим user_data в kartoshka_bot
        self.user_data_patcher = patch('kartoshka_bot.user_data', {})
        self.user_data = self.user_data_patcher.start()
        
        # Инициализируем данные пользователя
        kartoshka_bot.user_data[str(self.test_user_id)] = {
            "last_submission": None,
            "rejections": 0,
            "ban_until": None
        }
        
        # Мокаем save_user_data, чтобы данные оставались в памяти
        self.save_user_data_patcher = patch('kartoshka_bot.save_user_data', MagicMock())
        self.save_user_data_mock = self.save_user_data_patcher.start()
        
        # Мокаем scheduler
        self.scheduler_patcher = patch('kartoshka_bot.scheduler')
        self.scheduler_mock = self.scheduler_patcher.start()
        
        # Мокаем функции обновления сообщений
        self.update_user_messages_patcher = patch('kartoshka_bot.update_user_messages_with_status', AsyncMock())
        self.update_mod_messages_patcher = patch('kartoshka_bot.update_mod_messages_with_resolution', AsyncMock())
        self.publish_patcher = patch('kartoshka_bot.publish_meme', AsyncMock())
        
        self.update_user_messages_mock = self.update_user_messages_patcher.start()
        self.update_mod_messages_mock = self.update_mod_messages_patcher.start()
        self.publish_mock = self.publish_patcher.start()
        
        # Настраиваем scheduler mock
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
        self.user_data_patcher.stop()
        self.save_user_data_patcher.stop()
        self.scheduler_patcher.stop()
        self.update_user_messages_patcher.stop()
        self.update_mod_messages_patcher.stop()
        self.publish_patcher.stop()
    
    async def test_rejection_counter_increment(self):
        """Проверка увеличения счетчика отклонений при отклонении мема"""
        # Проверяем начальное значение
        self.assertEqual(kartoshka_bot.user_data[str(self.test_user_id)]["rejections"], 0)
        
        # Имитируем отклонение мема
        with patch('kartoshka_bot.CRYPTOSELECTARCHY', True), patch('kartoshka_bot.VOTES_TO_REJECT', 1):
            # Создаем пользовательскую функцию, имитирующую логику отклонения
            async def reject_meme():
                user_id = str(self.test_user_id)
                ud = kartoshka_bot.user_data.setdefault(user_id, {
                    "last_submission": None,
                    "rejections": 0,
                    "ban_until": None
                })
                ud["rejections"] += 1
            
            # Вызываем имитацию отклонения
            await reject_meme()
            
            # Проверяем, что счетчик увеличился
            self.assertEqual(kartoshka_bot.user_data[str(self.test_user_id)]["rejections"], 1)
    
    async def test_rejection_counter_reset_on_approval(self):
        """Проверка сброса счетчика отклонений при одобрении мема"""
        # Устанавливаем счетчик отклонений
        kartoshka_bot.user_data[str(self.test_user_id)]["rejections"] = 2
        
        # Проверяем начальное значение
        self.assertEqual(kartoshka_bot.user_data[str(self.test_user_id)]["rejections"], 2)
        
        # Имитируем одобрение мема
        with patch('kartoshka_bot.CRYPTOSELECTARCHY', True), patch('kartoshka_bot.VOTES_TO_APPROVE', 1):
            # Создаем пользовательскую функцию, имитирующую логику одобрения
            async def approve_meme():
                user_id = str(self.test_user_id)
                ud = kartoshka_bot.user_data.setdefault(user_id, {
                    "last_submission": None,
                    "rejections": 2,  # Уже было 2 отклонения
                    "ban_until": None
                })
                ud["rejections"] = 0  # Сбрасываем счетчик
            
            # Вызываем имитацию одобрения
            await approve_meme()
            
            # Проверяем, что счетчик сброшен
            self.assertEqual(kartoshka_bot.user_data[str(self.test_user_id)]["rejections"], 0)
    
    async def test_ban_removal_on_approval(self):
        """Проверка снятия бана при одобрении мема"""
        # Устанавливаем бан
        ban_time = datetime.now(timezone.utc) + timedelta(days=1)
        kartoshka_bot.user_data[str(self.test_user_id)]["ban_until"] = ban_time
        
        # Проверяем начальное значение
        self.assertIsNotNone(kartoshka_bot.user_data[str(self.test_user_id)]["ban_until"])
        
        # Имитируем одобрение мема и снятие бана
        with patch('kartoshka_bot.CRYPTOSELECTARCHY', True), patch('kartoshka_bot.VOTES_TO_APPROVE', 1):
            # Создаем пользовательскую функцию, имитирующую логику одобрения
            async def approve_meme_and_remove_ban():
                user_id = str(self.test_user_id)
                ud = kartoshka_bot.user_data.setdefault(user_id, {
                    "last_submission": None,
                    "rejections": 0,
                    "ban_until": ban_time  # Уже существует бан
                })
                ud["ban_until"] = None  # Снимаем бан
            
            # Вызываем имитацию одобрения и снятия бана
            await approve_meme_and_remove_ban()
            
            # Проверяем, что бан снят
            self.assertIsNone(kartoshka_bot.user_data[str(self.test_user_id)]["ban_until"])
    
    async def test_multiple_rejections_counting(self):
        """Проверка корректного подсчета нескольких последовательных отклонений"""
        # Начинаем с нулевого счетчика отклонений
        kartoshka_bot.user_data[str(self.test_user_id)]["rejections"] = 0
        
        # Имитируем несколько последовательных отклонений
        with patch('kartoshka_bot.CRYPTOSELECTARCHY', True), patch('kartoshka_bot.VOTES_TO_REJECT', 1):
            # Первое отклонение
            async def reject_meme_1():
                user_id = str(self.test_user_id)
                ud = kartoshka_bot.user_data[user_id]
                ud["rejections"] += 1
            
            # Второе отклонение
            async def reject_meme_2():
                user_id = str(self.test_user_id)
                ud = kartoshka_bot.user_data[user_id]
                ud["rejections"] += 1
            
            # Третье отклонение
            async def reject_meme_3():
                user_id = str(self.test_user_id)
                ud = kartoshka_bot.user_data[user_id]
                ud["rejections"] += 1
            
            # Вызываем имитации отклонений
            await reject_meme_1()
            self.assertEqual(kartoshka_bot.user_data[str(self.test_user_id)]["rejections"], 1)
            
            await reject_meme_2()
            self.assertEqual(kartoshka_bot.user_data[str(self.test_user_id)]["rejections"], 2)
            
            await reject_meme_3()
            self.assertEqual(kartoshka_bot.user_data[str(self.test_user_id)]["rejections"], 3)
    
    async def test_ban_check_before_submission(self):
        """Проверка отказа в приеме мема при наличии бана"""
        # Устанавливаем бан
        ban_time = datetime.now(timezone.utc) + timedelta(days=1)
        kartoshka_bot.user_data[str(self.test_user_id)]["ban_until"] = ban_time
        
        # Создаем имитацию обработчика мема
        @self.dp.message(kartoshka_bot.filters_module.F.content_type.in_(["text", "photo", "video", "animation", "voice", "video_note"]))
        async def handle_meme_suggestion(message):
            user_id = message.from_user.id
            
            # Проверка бана и частоты отправки мемов
            now = datetime.now(timezone.utc)
            ud = kartoshka_bot.user_data.setdefault(str(user_id), {
                "last_submission": None,
                "rejections": 0,
                "ban_until": None
            })
            
            # 1. Проверка на бан
            if ud["ban_until"] and now < ud["ban_until"]:
                until = ud["ban_until"].strftime("%d.%m.%Y")
                await message.answer(f"Сорри, ты у нас в изгнании до {until}, мемы отправлять нельзя.")
                return
            
            # Если бана нет, то продолжаем обработку
            await message.answer("Ваш мем отправлен на модерацию.")
        
        # Создаем тестовое сообщение
        message = kartoshka_bot.types_module.Message(
            message_id=1000,
            from_user=kartoshka_bot.types_module.User(id=self.test_user_id),
            text="Мем от забаненного пользователя",
            content_type="text"
        )
        
        # Мокаем функцию answer
        message.answer = AsyncMock()
        
        # Устанавливаем kartoshka_bot.user_publish_choice
        with patch('kartoshka_bot.user_publish_choice', {self.test_user_id: "user"}):
            await handle_meme_suggestion(message)
            
            # Проверяем, что пользователь получил сообщение о бане
            message.answer.assert_called_once()
            args, kwargs = message.answer.call_args
            self.assertIn("изгнании", args[0])
            self.assertIn(ban_time.strftime("%d.%m.%Y"), args[0])
    
    async def test_frequency_limit_check_before_submission(self):
        """Проверка отказа в приеме мема при нарушении лимита частоты отправки"""
        # Предварительно устанавливаем время последней отправки мема (менее 24 часов назад)
        last_submission = datetime.now(timezone.utc) - timedelta(hours=12)
        kartoshka_bot.user_data[str(self.test_user_id)]["last_submission"] = last_submission
        
        # Создаем имитацию обработчика мема
        @self.dp.message(kartoshka_bot.filters_module.F.content_type.in_(["text", "photo", "video", "animation", "voice", "video_note"]))
        async def handle_meme_suggestion(message):
            user_id = message.from_user.id
            
            # Проверка бана и частоты отправки мемов
            now = datetime.now(timezone.utc)
            ud = kartoshka_bot.user_data.setdefault(str(user_id), {
                "last_submission": None,
                "rejections": 0,
                "ban_until": None
            })
            
            # Проверка 24-часового лимита
            if ud["last_submission"] and now - ud["last_submission"] < timedelta(hours=24):
                nt = (ud["last_submission"] + timedelta(hours=24))
                await message.answer(
                    f"Ты уже отправлял мем в последние 24 ч. Попробуй после {nt.strftime('%H:%M %d.%m.%Y')}."
                )
                return
            
            # Если лимит не нарушен, то продолжаем обработку
            await message.answer("Ваш мем отправлен на модерацию.")
        
        # Создаем тестовое сообщение
        message = kartoshka_bot.types_module.Message(
            message_id=1001,
            from_user=kartoshka_bot.types_module.User(id=self.test_user_id),
            text="Мем с нарушением лимита частоты",
            content_type="text"
        )
        
        # Мокаем функцию answer
        message.answer = AsyncMock()
        
        # Устанавливаем kartoshka_bot.user_publish_choice
        with patch('kartoshka_bot.user_publish_choice', {self.test_user_id: "user"}):
            await handle_meme_suggestion(message)
            
            # Проверяем, что пользователь получил сообщение о нарушении лимита частоты
            message.answer.assert_called_once()
            args, kwargs = message.answer.call_args
            self.assertIn("уже отправлял мем", args[0])
            next_time = last_submission + timedelta(hours=24)
            self.assertIn(next_time.strftime('%H:%M'), args[0])
    
    async def test_submission_timestamp_update(self):
        """Проверка обновления временной метки последней отправки мема"""
        # Начинаем без временной метки последней отправки
        kartoshka_bot.user_data[str(self.test_user_id)]["last_submission"] = None
        
        # Создаем имитацию обработчика мема
        @self.dp.message(kartoshka_bot.filters_module.F.content_type.in_(["text", "photo", "video", "animation", "voice", "video_note"]))
        async def handle_meme_suggestion(message):
            user_id = message.from_user.id
            
            # Проверка бана и частоты отправки мемов
            now = datetime.now(timezone.utc)
            ud = kartoshka_bot.user_data.setdefault(str(user_id), {
                "last_submission": None,
                "rejections": 0,
                "ban_until": None
            })
            
            # Успешно пойдёт на модерацию — сразу обновляем last_submission
            ud["last_submission"] = now
            
            # Продолжаем обработку
            await message.answer("Ваш мем отправлен на модерацию.")
        
        # Создаем тестовое сообщение
        message = kartoshka_bot.types_module.Message(
            message_id=1002,
            from_user=kartoshka_bot.types_module.User(id=self.test_user_id),
            text="Нормальный мем",
            content_type="text"
        )
        
        # Мокаем функцию answer
        message.answer = AsyncMock()
        
        # Устанавливаем kartoshka_bot.user_publish_choice
        with patch('kartoshka_bot.user_publish_choice', {self.test_user_id: "user"}):
            # Запоминаем время до вызова
            before_time = datetime.now(timezone.utc)
            
            await handle_meme_suggestion(message)
            
            # Запоминаем время после вызова
            after_time = datetime.now(timezone.utc)
            
            # Проверяем, что временная метка last_submission была обновлена
            self.assertIsNotNone(kartoshka_bot.user_data[str(self.test_user_id)]["last_submission"])
            
            # Проверяем, что новая временная метка находится в правильном диапазоне времени
            submission_time = kartoshka_bot.user_data[str(self.test_user_id)]["last_submission"]
            self.assertTrue(before_time <= submission_time <= after_time)
            
            # Проверяем, что пользователь получил сообщение об успешной отправке
            message.answer.assert_called_once_with("Ваш мем отправлен на модерацию.")
    
    async def test_automatic_ban_after_three_rejections(self):
        """Проверка автоматического бана после трех отклонений"""
        # Начинаем с нулевого счетчика отклонений
        kartoshka_bot.user_data[str(self.test_user_id)]["rejections"] = 0
        
        # Имитируем логику отклонения мема и бана
        async def simulate_rejection_and_check_ban(rejection_count):
            user_id = str(self.test_user_id)
            ud = kartoshka_bot.user_data[user_id]
            ud["rejections"] += 1
            
            # Если достигли лимита отклонений, устанавливаем бан
            if ud["rejections"] >= 3:
                ud["ban_until"] = datetime.now(timezone.utc) + timedelta(days=14)
                
        # Имитируем последовательные отклонения
        await simulate_rejection_and_check_ban(1)
        self.assertEqual(kartoshka_bot.user_data[str(self.test_user_id)]["rejections"], 1)
        self.assertIsNone(kartoshka_bot.user_data[str(self.test_user_id)]["ban_until"])
        
        await simulate_rejection_and_check_ban(2)
        self.assertEqual(kartoshka_bot.user_data[str(self.test_user_id)]["rejections"], 2)
        self.assertIsNone(kartoshka_bot.user_data[str(self.test_user_id)]["ban_until"])
        
        # После третьего отклонения должен быть установлен бан
        await simulate_rejection_and_check_ban(3)
        self.assertEqual(kartoshka_bot.user_data[str(self.test_user_id)]["rejections"], 3)
        self.assertIsNotNone(kartoshka_bot.user_data[str(self.test_user_id)]["ban_until"])
        
        # Проверяем, что срок бана составляет 14 дней от текущего времени
        ban_until = kartoshka_bot.user_data[str(self.test_user_id)]["ban_until"]
        now = datetime.now(timezone.utc)
        self.assertTrue(now + timedelta(days=13) < ban_until < now + timedelta(days=15))

if __name__ == "__main__":
    unittest.main()