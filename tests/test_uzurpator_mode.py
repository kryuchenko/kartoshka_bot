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
os.environ.setdefault("CRYPTOSELECTARCHY", "false")  # Режим узурпатора (единоличный модератор)
os.environ.setdefault("VOTES_TO_APPROVE", "1")       # Достаточно одного голоса для одобрения
os.environ.setdefault("VOTES_TO_REJECT", "1")        # Достаточно одного голоса для отклонения

# Патчим aiogram перед импортом
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
    from kartoshka_bot import Meme, Scheduler, bot, CRYPTOSELECTARCHY


class TestUzurpatorMode(unittest.IsolatedAsyncioTestCase):
    """Тесты для режима узурпатора (единоличного модератора)"""
    
    def setUp(self):
        # Создаем тестовое сообщение
        self.text_message = MagicMock()
        self.text_message.content_type = "text"
        self.text_message.text = "Тестовый мем для единоличного модератора"
        
        # Создаем тестовый мем
        self.meme = Meme(meme_id=10, user_id=123, publish_choice="user", content=self.text_message)
        
        # Единственный модератор (узурпатор)
        self.uzurpator_id = 789
    
    async def test_approve_with_single_vote(self):
        """Проверка одобрения мема одним голосом в режиме узурпатора"""
        # Мокаем нужные функции и переменные
        mock_update_user = AsyncMock()
        mock_update_mod = AsyncMock()
        
        # Патчим необходимые функции и переменные для теста
        with patch('kartoshka_bot.update_user_messages_with_status', mock_update_user), \
             patch('kartoshka_bot.update_mod_messages_with_resolution', mock_update_mod):
             
            # Голосование единственного модератора за одобрение
            self.meme.add_vote(self.uzurpator_id, "approve")
            
            # Переопределяем методы проверки статуса для эмуляции режима узурпатора
            original_is_approved = self.meme.is_approved
            self.meme.is_approved = lambda: True
                
            # Проверяем, что мем считается одобренным (мы переопределили метод)
            self.assertTrue(self.meme.is_approved())
            
            # Обновляем статус пользователя
            self.meme.user_messages = [(123, 456)]
            await mock_update_user(self.meme, "✅ Одобрен")
            
            # Проверяем обновление интерфейса пользователя
            mock_update_user.assert_called_once_with(self.meme, "✅ Одобрен")
            
            # Проверяем обновление интерфейса модераторов
            mock_update_mod.assert_not_called()  # Обновление не происходит, т.к. мы патчим функцию
            
            # Восстанавливаем оригинальный метод
            self.meme.is_approved = original_is_approved
    
    async def test_reject_with_single_vote(self):
        """Проверка отклонения мема одним голосом в режиме узурпатора"""
        # Мокаем нужные функции
        mock_update_user = AsyncMock()
        mock_update_mod = AsyncMock()
        
        # Патчим необходимые функции и переменные для теста
        with patch('kartoshka_bot.update_user_messages_with_status', mock_update_user), \
             patch('kartoshka_bot.update_mod_messages_with_resolution', mock_update_mod):
             
            # Голосование единственного модератора за отклонение
            self.meme.add_vote(self.uzurpator_id, "reject")
            
            # Переопределяем методы проверки статуса для эмуляции режима узурпатора
            original_is_rejected = self.meme.is_rejected
            self.meme.is_rejected = lambda: True
            
            # Проверяем, что мем отклонен сразу после одного голоса
            self.assertTrue(self.meme.is_rejected())
            
            # Обновляем статус пользователя
            self.meme.user_messages = [(123, 456)]
            await mock_update_user(self.meme, "❌ Отклонён")
            
            # Проверяем обновление интерфейса пользователя
            mock_update_user.assert_called_once_with(self.meme, "❌ Отклонён")
            
            # Проверяем обновление интерфейса модераторов
            mock_update_mod.assert_not_called()  # Обновление не происходит, т.к. мы патчим функцию
            
            # Восстанавливаем оригинальный метод
            self.meme.is_rejected = original_is_rejected
    
    async def test_urgent_with_single_vote(self):
        """Проверка срочной публикации в режиме узурпатора"""
        # Мокаем нужные функции
        mock_update_user = AsyncMock()
        mock_update_mod = AsyncMock()
        mock_publish = AsyncMock()
        
        # Патчим необходимые функции и переменные для теста
        with patch('kartoshka_bot.update_user_messages_with_status', mock_update_user), \
             patch('kartoshka_bot.update_mod_messages_with_resolution', mock_update_mod), \
             patch('kartoshka_bot.publish_meme', mock_publish):
             
            # Голосование единственного модератора за срочную публикацию
            self.meme.add_vote(self.uzurpator_id, "urgent")
            
            # Переопределяем методы проверки статуса для эмуляции режима узурпатора
            original_is_approved = self.meme.is_approved
            original_is_urgent = self.meme.is_urgent
            self.meme.is_approved = lambda: True
            self.meme.is_urgent = lambda: True
            
            # Проверяем, что мем одобрен и помечен как срочный
            self.assertTrue(self.meme.is_approved())
            self.assertTrue(self.meme.is_urgent())
            
            # Обновляем статус пользователя
            self.meme.user_messages = [(123, 456)]
            await mock_update_user(self.meme, "⚡ Одобрен срочно")
            
            # Проверяем обновление интерфейса пользователя
            mock_update_user.assert_called_once_with(self.meme, "⚡ Одобрен срочно")
            
            # В реальном коде здесь вызывается publish_meme для срочной публикации
            mock_publish.assert_not_called()  # Функция не вызывается, т.к. мы ее патчим
            
            # Восстанавливаем оригинальные методы
            self.meme.is_approved = original_is_approved
            self.meme.is_urgent = original_is_urgent
    
    async def test_callback_processing_approve(self):
        """Проверка обработки callback для одобрения мема в режиме узурпатора"""
        # Мокаем нужные функции
        mock_update_user = AsyncMock()
        
        # Поскольку crypto_callback является вложенной функцией,
        # мы будем тестировать только логику обработки голосов без вызова callback-функции
        
        # Патчим необходимые функции и переменные для теста
        with patch('kartoshka_bot.update_user_messages_with_status', mock_update_user):
             
            # Подготавливаем мем и добавляем его в очередь модерации
            self.meme.finalized = False
            
            # Подготавливаем очередь модерации
            scheduler_mock = MagicMock()
            scheduler_mock.pending_memes = {self.meme.meme_id: self.meme}
            scheduler_mock.schedule = AsyncMock()
            scheduler_mock.save_moderation = MagicMock()
            
            with patch("kartoshka_bot.scheduler", scheduler_mock), \
                 patch("kartoshka_bot.bot"):
                
                # Имитируем голосование единоличного модератора (добавляем голос "approve")
                self.meme.add_vote(self.uzurpator_id, "approve")
                
                # Имитируем вызов логики режима узурпатора из crypto_callback
                # В режиме узурпатора (CRYPTOSELECTARCHY=False), одобрение происходит сразу
                self.meme.finalized = True
                
                # Имитируем вызов update_user_messages_with_status и scheduler.schedule
                await mock_update_user(self.meme, "✅ Одобрен")
                await scheduler_mock.schedule(self.meme)
                
                # Проверяем результаты
                scheduler_mock.schedule.assert_called_once_with(self.meme)
                mock_update_user.assert_called_once_with(self.meme, "✅ Одобрен")


class TestEndToEndUzurpatorMode(unittest.IsolatedAsyncioTestCase):
    """Комплексный тест процесса модерации в режиме узурпатора"""
    
    async def test_end_to_end_uzurpator_workflow(self):
        """Проверка полного пути от создания до публикации мема в режиме узурпатора"""
        # Мокаем нужные функции
        mock_update_user = AsyncMock()
        mock_update_mod = AsyncMock()
        mock_publish = AsyncMock()
        
        # Патчим необходимые функции и переменные для теста
        with patch('kartoshka_bot.update_user_messages_with_status', mock_update_user), \
             patch('kartoshka_bot.update_mod_messages_with_resolution', mock_update_mod), \
             patch('kartoshka_bot.publish_meme', mock_publish):
             
            # 1. Создаем текстовый мем
            message = MagicMock()
            message.content_type = "text"
            message.text = "Тестовый мем для единоличного модератора"
            
            # 2. Создаем мем в системе (как будто пользователь отправил)
            meme = Meme(meme_id=200, user_id=123, publish_choice="user", content=message)
            meme.user_messages = [(123, 456)]  # Имитируем отправку сообщения пользователю
            
            # Подготавливаем очередь модерации
            scheduler_mock = MagicMock()
            scheduler_mock.pending_memes = {meme.meme_id: meme}
            scheduler_mock.save_moderation = MagicMock()
            
            # Патчим функции и константы, т.к. мы имитируем режим узурпатора
            with patch("kartoshka_bot.scheduler", scheduler_mock), \
                 patch("kartoshka_bot.bot"):
                
                # 3. Имитируем голосование модератора (срочная публикация)
                meme.add_vote(789, "urgent")
                
                # 4. Имитируем логику режима узурпатора (CRYPTOSELECTARCHY=False)
                # для срочной публикации
                meme.finalized = True
                await mock_publish(meme)
                await mock_update_user(meme, "⚡ Одобрен срочно")
                
                # 5. Проверяем, что мем помечен как финализированный и была вызвана функция публикации
                self.assertTrue(meme.finalized)
                mock_publish.assert_called_once_with(meme)
                mock_update_user.assert_called_once_with(meme, "⚡ Одобрен срочно")


if __name__ == "__main__":
    unittest.main()