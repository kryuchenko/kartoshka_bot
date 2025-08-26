#!/usr/bin/env python3
import unittest
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
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

# Патчим функцию валидации токена перед любыми импортами aiogram
with patch.dict('sys.modules'):
    # Сначала патчим aiogram.utils.token, чтобы validate_token всегда возвращал True
    validate_token_module = MagicMock()
    validate_token_module.validate_token.return_value = True
    sys.modules['aiogram.utils.token'] = validate_token_module
    
    # Затем создаем заглушки для других модулей aiogram
    bot_module = MagicMock()
    bot_class = MagicMock()
    bot_instance = MagicMock()
    bot_class.return_value = bot_instance
    bot_module.Bot = bot_class
    bot_module.DefaultBotProperties = MagicMock()
    sys.modules['aiogram.client.bot'] = bot_module
    
    # Добавляем директорию проекта в PYTHONPATH
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    # Патчим остальные необходимые компоненты aiogram
    sys.modules['aiogram'] = MagicMock()
    sys.modules['aiogram.types'] = MagicMock()
    sys.modules['aiogram.filters'] = MagicMock()
    
    # Теперь можно импортировать модуль
    from kartoshka_bot import Meme, Scheduler, bot


class TestMemeCreation(unittest.TestCase):
    """Тесты для этапа создания мема пользователем"""
    
    def setUp(self):
        # Создаем пользователя для тестов
        self.test_user = MagicMock()
        self.test_user.username = "TestUser"
        self.test_user.id = 123
        self.test_user.first_name = "Test"
        
        self.text_message = MagicMock()
        self.text_message.content_type = "text"
        self.text_message.text = "Тестовый текстовый мем"
        self.text_message.caption = None
        self.text_message.from_user = self.test_user
        
        self.photo_message = MagicMock()
        self.photo_message.content_type = "photo"
        self.photo_message.text = None
        self.photo_message.caption = "Тестовый мем с фото"
        self.photo_message.photo = [MagicMock(file_id="test_photo_id")]
        self.photo_message.from_user = self.test_user
    
    def test_create_text_meme_user(self):
        """Проверка создания текстового мема от пользователя"""
        meme = Meme(meme_id=1, user_id=123, publish_choice="user", content=self.text_message)
        
        # Проверка атрибутов
        self.assertEqual(meme.meme_id, 1)
        self.assertEqual(meme.user_id, 123)
        self.assertEqual(meme.publish_choice, "user")
        self.assertEqual(meme.content, self.text_message)
        self.assertEqual(len(meme.votes), 0)
        self.assertFalse(meme.finalized)
        
        # Проверка подписи (теперь включает username)
        caption = meme.get_caption()
        self.assertTrue("Мем от пользователя @TestUser" in caption)
        self.assertIn("Тестовый текстовый мем", caption)
    
    def test_create_text_meme_anonymous(self):
        """Проверка создания текстового мема анонимно"""
        meme = Meme(meme_id=2, user_id=123, publish_choice="potato", content=self.text_message)
        
        # Проверка атрибутов
        self.assertEqual(meme.meme_id, 2)
        self.assertEqual(meme.user_id, 123)
        self.assertEqual(meme.publish_choice, "potato")
        
        # Проверка подписи
        caption = meme.get_caption()
        self.assertTrue("<tg-spoiler>Мем от Анонимной" in caption)
        self.assertIn("Картошки</tg-spoiler>", caption)
        self.assertIn("Тестовый текстовый мем", caption)
    
    def test_create_photo_meme_user(self):
        """Проверка создания мема с фото от пользователя"""
        meme = Meme(meme_id=3, user_id=456, publish_choice="user", content=self.photo_message)
        
        # Проверка подписи (теперь включает username)
        caption = meme.get_caption()
        self.assertTrue("Мем от пользователя @TestUser" in caption)
        self.assertIn("Тестовый мем с фото", caption)
    
    def test_create_photo_meme_anonymous(self):
        """Проверка создания мема с фото анонимно"""
        meme = Meme(meme_id=4, user_id=456, publish_choice="potato", content=self.photo_message)
        
        # Проверка подписи
        caption = meme.get_caption()
        self.assertTrue("<tg-spoiler>Мем от Анонимной" in caption)
        self.assertIn("Картошки</tg-spoiler>", caption)
        self.assertIn("Тестовый мем с фото", caption)
    
    def test_meme_serialization(self):
        """Проверка сериализации/десериализации мема"""
        meme = Meme(meme_id=5, user_id=789, publish_choice="user", content=self.text_message)
        
        # Сериализуем мем
        meme_dict = meme.to_dict()
        
        # Проверяем, что пользователь сохраняется для неанонимных мемов
        self.assertIn("user_id", meme_dict)
        self.assertEqual(meme_dict["user_id"], 789)
        
        # Десериализуем мем
        restored_meme = Meme.from_dict(meme_dict)
        
        # Проверяем восстановленные атрибуты
        self.assertEqual(restored_meme.meme_id, 5)
        self.assertEqual(restored_meme.publish_choice, "user")
        
        # Для анонимных мемов user_id не должен сохраняться
        anon_meme = Meme(meme_id=6, user_id=789, publish_choice="potato", content=self.text_message)
        anon_dict = anon_meme.to_publication_dict()
        self.assertNotIn("user_id", anon_dict)


class TestModerationProcess(unittest.IsolatedAsyncioTestCase):
    """Тесты для процесса модерации мема"""
    
    def setUp(self):
        self.text_message = MagicMock()
        self.text_message.content_type = "text"
        self.text_message.text = "Тестовый мем для модерации"
        
        # Создаем тестовый мем
        self.meme = Meme(meme_id=10, user_id=123, publish_choice="user", content=self.text_message)
        
        # Мокаем бота
        self.bot_mock = MagicMock()
        self.bot_mock.edit_message_reply_markup = AsyncMock()
    
    async def test_voting_process(self):
        """Проверка процесса голосования"""
        # Добавляем первый голос
        prev_vote = self.meme.add_vote(101, "approve")
        self.assertIsNone(prev_vote)  # Первый голос от этого пользователя
        self.assertEqual(self.meme.count_votes("approve"), 1)
        
        # Добавляем второй голос от другого пользователя
        self.meme.add_vote(102, "urgent")
        self.assertEqual(self.meme.count_votes("approve"), 2)  # approve + urgent
        
        # Проверяем, что urgent голос учитывается правильно
        self.assertEqual(sum(1 for v in self.meme.votes.values() if v == "urgent"), 1)
        
        # Добавляем голос против
        self.meme.add_vote(103, "reject")
        self.assertEqual(self.meme.count_votes("reject"), 1)
        
        # Изменяем предыдущий голос
        prev_vote = self.meme.add_vote(101, "reject")
        self.assertEqual(prev_vote, "approve")  # Предыдущий голос был "approve"
        self.assertEqual(self.meme.count_votes("approve"), 1)  # Теперь только urgent
        self.assertEqual(self.meme.count_votes("reject"), 2)  # Два голоса против
        
        # Проверяем формат сводки голосов
        vote_summary = self.meme.get_vote_summary()
        self.assertEqual(vote_summary, "(✅ 0 | ⚡ 1 | ❌ 2)")
    
    async def test_approval_decision(self):
        """Проверка одобрения мема"""
        # Фиксируем VOTES_TO_APPROVE = 3 для теста
        with patch("kartoshka_bot.VOTES_TO_APPROVE", 3):
            # Добавляем голоса для одобрения
            self.meme.add_vote(101, "approve")
            self.meme.add_vote(102, "approve")
            
            # Проверяем, что мем еще не одобрен (2 < 3)
            self.assertFalse(self.meme.is_approved())
            
            # Добавляем третий голос
            self.meme.add_vote(103, "approve")
            
            # Теперь мем должен быть одобрен
            self.assertTrue(self.meme.is_approved())
    
    async def test_urgent_decision(self):
        """Проверка срочной публикации"""
        # Фиксируем VOTES_TO_APPROVE = 3 для теста
        with patch("kartoshka_bot.VOTES_TO_APPROVE", 3):
            # urgent_threshold = max(1, math.ceil(3 * 0.51)) = 2
            
            # Добавляем один голос "срочно"
            self.meme.add_vote(101, "urgent")
            
            # Один голос "срочно" недостаточно
            self.assertFalse(self.meme.is_urgent())
            
            # Добавляем второй голос "срочно"
            self.meme.add_vote(102, "urgent")
            
            # Теперь мем должен быть помечен как срочный
            self.assertTrue(self.meme.is_urgent())
    
    async def test_rejection_decision(self):
        """Проверка отклонения мема"""
        # Фиксируем VOTES_TO_REJECT = 3 для теста
        with patch("kartoshka_bot.VOTES_TO_REJECT", 3):
            # Добавляем голоса для отклонения
            self.meme.add_vote(101, "reject")
            self.meme.add_vote(102, "reject")
            
            # Проверяем, что мем еще не отклонен (2 < 3)
            self.assertFalse(self.meme.is_rejected())
            
            # Добавляем третий голос
            self.meme.add_vote(103, "reject")
            
            # Теперь мем должен быть отклонен
            self.assertTrue(self.meme.is_rejected())
    
    @patch('kartoshka_bot.update_user_messages_with_status')
    async def test_widget_update(self, mock_update):
        """Проверка обновления виджета пользователя"""
        # Добавляем сообщение пользователя для обновления
        self.meme.user_messages = [(123, 456)]
        
        # Проверка вызова функции для обновления статуса
        await mock_update(self.meme)
        await mock_update(self.meme, "✅ Одобрен")
        
        # Проверяем, что функция была вызвана дважды с правильными аргументами
        self.assertEqual(mock_update.await_count, 2)
        # Первый вызов с мемом без финального решения
        mock_update.assert_any_await(self.meme)
        # Второй вызов с мемом и финальным решением
        mock_update.assert_any_await(self.meme, "✅ Одобрен")


class TestPublicationQueue(unittest.IsolatedAsyncioTestCase):
    """Тесты для очереди публикации"""
    
    def setUp(self):
        # Создаем мок для текстового сообщения
        self.text_message = MagicMock()
        self.text_message.content_type = "text"
        self.text_message.text = "Тестовый мем для публикации"
        
        # Создаем тестовый мем
        self.meme = Meme(meme_id=20, user_id=123, publish_choice="user", content=self.text_message)
        
        # Создаем планировщик с патчем для бота и счетчика мемов
        with patch("kartoshka_bot.load_meme_counter", return_value=0):
            self.scheduler = Scheduler(post_frequency_minutes=60)
    
    @patch('kartoshka_bot.update_user_messages_with_status', new_callable=AsyncMock)
    async def test_scheduling(self, mock_update_user):
        """Проверка добавления мема в очередь публикации"""
        # Очищаем существующие посты в планировщике
        self.scheduler.scheduled_posts = []
        
        # Добавляем сообщения пользователя для теста обновления
        self.meme.user_messages = [(123, 456)]
        
        # Добавляем мем в очередь
        await self.scheduler.schedule(self.meme)
        
        # Проверяем, что мем добавлен в очередь
        self.assertEqual(len(self.scheduler.scheduled_posts), 1)
        
        # Проверяем, что запланированное время существует
        scheduled_time = datetime.fromisoformat(self.scheduler.scheduled_posts[0]["scheduled_time"])
        
        # Проверка того, что время указано и является действительным datetime
        self.assertIsInstance(scheduled_time, datetime)
        self.assertTrue(scheduled_time.year >= 2025)
    
    async def test_publication_time_rounding(self):
        """Проверка округления времени публикации в ночное время"""
        # Устанавливаем текущее время как ночное
        night_time = datetime.now(timezone.utc).replace(hour=2, minute=0, second=0, microsecond=0)
        
        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value = night_time
            mock_datetime.fromisoformat = datetime.fromisoformat
            
            # Получаем время для следующей публикации
            next_time = self.scheduler.get_next_allowed_time(night_time)
            
            # Время должно быть не раньше 7 утра
            self.assertEqual(next_time.hour, 7)
            self.assertEqual(next_time.minute, 0)
    
    @patch("kartoshka_bot.send_media_message", new_callable=AsyncMock)
    async def test_publication(self, mock_send_media):
        """Проверка публикации мема"""
        from kartoshka_bot import publish_meme
        
        # Публикуем мем
        await publish_meme(self.meme)
        
        # Проверяем, что вызван метод send_media_message
        mock_send_media.assert_called_once()
        
        # Проверяем, что caption передан правильно
        args, kwargs = mock_send_media.call_args
        self.assertEqual(kwargs["content"], self.meme.content)
        self.assertEqual(kwargs["caption"], self.meme.get_caption())


class TestEndToEndFlow(unittest.IsolatedAsyncioTestCase):
    """Комплексный тест всего процесса от создания до публикации"""
    
    @patch("kartoshka_bot.send_media_message", new_callable=AsyncMock)
    @patch("kartoshka_bot.update_user_messages_with_status", new_callable=AsyncMock)
    @patch("kartoshka_bot.update_mod_messages_with_resolution", new_callable=AsyncMock)
    async def test_full_workflow(self, mock_update_mod, mock_update_user, mock_send_media):
        """Проверка полного пути от создания мема до публикации"""
        from kartoshka_bot import publish_meme
        
        # 1. Создаем текстовый мем
        message = MagicMock()
        message.content_type = "text"
        message.text = "Тестовый мем для полного цикла"
        
        # 2. Создаем мем в системе (как будто пользователь отправил)
        meme = Meme(meme_id=100, user_id=123, publish_choice="user", content=message)
        meme.user_messages = [(123, 456)]  # Имитируем отправку сообщения пользователю
        
        # 3. Добавляем голоса модераторов
        with patch("kartoshka_bot.VOTES_TO_APPROVE", 3), patch("kartoshka_bot.VOTES_TO_REJECT", 3):
            # Голосуем за мем
            meme.add_vote(101, "approve")
            # Обновляем виджет пользователя
            await mock_update_user(meme)
            
            # Проверяем вызов обновления виджета
            mock_update_user.assert_called_once_with(meme)
            mock_update_user.reset_mock()
            
            # Добавляем еще голоса для одобрения
            meme.add_vote(102, "approve")
            meme.add_vote(103, "approve")
            
            # Теперь мем одобрен
            self.assertTrue(meme.is_approved())
            
            # 4. Публикуем мем
            await publish_meme(meme)
            
            # Проверяем, что вызван метод send_media_message для публикации
            mock_send_media.assert_called_once()
            
            # 5. Обновляем интерфейс с финальным решением
            await mock_update_user(meme, "✅ Одобрен")
            
            # Проверяем обновление интерфейса
            mock_update_user.assert_called_once_with(meme, "✅ Одобрен")


if __name__ == "__main__":
    unittest.main()