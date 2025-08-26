#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import MagicMock
from types import SimpleNamespace
import json

# Импортируем нужные классы
from kartoshka_bot import Meme

class TestUserPrivacy(unittest.TestCase):
    """Тесты для проверки приватности пользователей"""
    
    def setUp(self):
        # Создаем тестового пользователя
        self.user = MagicMock()
        self.user.id = 12345
        self.user.username = "secretuser"
        self.user.first_name = "Secret"
        
        # Создаем тестовое сообщение
        self.message = MagicMock()
        self.message.content_type = "text"
        self.message.text = "Тестовый мем"
        self.message.caption = None
        self.message.from_user = self.user
    
    def test_non_anonymous_meme_preserves_user_data(self):
        """Неанонимный мем должен сохранять данные пользователя"""
        # Создаем неанонимный мем
        meme = Meme(meme_id=1, user_id=12345, publish_choice="user", content=self.message)
        
        # Проверяем caption
        caption = meme.get_caption()
        self.assertIn("@secretuser", caption, "Username должен быть в caption")
        
        # Проверяем сериализацию
        meme_dict = meme.to_dict()
        
        # Данные пользователя должны сохраняться
        self.assertIn("from_user", meme_dict["content"], "from_user должен быть сохранен")
        self.assertEqual(meme_dict["content"]["from_user"]["username"], "secretuser")
        self.assertEqual(meme_dict["content"]["from_user"]["first_name"], "Secret")
        self.assertIn("user_id", meme_dict, "user_id должен быть сохранен")
        
        # Проверяем publication dict
        pub_dict = meme.to_publication_dict()
        self.assertIn("from_user", pub_dict["content"], "from_user должен быть в publication dict")
        
        print("✅ Неанонимный мем: данные пользователя СОХРАНЯЮТСЯ")
    
    def test_anonymous_meme_hides_user_data(self):
        """Анонимный мем НЕ должен сохранять данные пользователя"""
        # Создаем анонимный мем
        meme = Meme(meme_id=2, user_id=12345, publish_choice="potato", content=self.message)
        
        # Проверяем caption
        caption = meme.get_caption()
        self.assertNotIn("@secretuser", caption, "Username НЕ должен быть в caption")
        self.assertNotIn("Secret", caption, "Имя НЕ должно быть в caption")
        self.assertIn("Картошки</tg-spoiler>", caption, "Должна быть анонимная подпись")
        
        # Проверяем сериализацию
        meme_dict = meme.to_dict()
        
        # Данные пользователя НЕ должны сохраняться
        self.assertNotIn("from_user", meme_dict["content"], "from_user НЕ должен быть сохранен")
        self.assertNotIn("user_id", meme_dict, "user_id НЕ должен быть сохранен для анонима")
        
        # Проверяем publication dict
        pub_dict = meme.to_publication_dict()
        self.assertNotIn("from_user", pub_dict["content"], "from_user НЕ должен быть в publication dict")
        
        print("✅ Анонимный мем: данные пользователя НЕ СОХРАНЯЮТСЯ")
    
    def test_user_without_username(self):
        """Проверка мема от пользователя без username"""
        # Создаем пользователя без username
        user_no_username = MagicMock()
        user_no_username.id = 67890
        user_no_username.username = None
        user_no_username.first_name = "OnlyName"
        
        message = MagicMock()
        message.content_type = "text"
        message.text = "Мем без username"
        message.caption = None
        message.from_user = user_no_username
        
        # Неанонимный мем
        meme = Meme(meme_id=3, user_id=67890, publish_choice="user", content=message)
        
        # Проверяем caption
        caption = meme.get_caption()
        self.assertIn("OnlyName", caption, "Должно отображаться имя")
        self.assertNotIn("@", caption, "Не должно быть @")
        
        # Проверяем сериализацию
        meme_dict = meme.to_dict()
        self.assertIn("from_user", meme_dict["content"])
        self.assertIsNone(meme_dict["content"]["from_user"]["username"])
        self.assertEqual(meme_dict["content"]["from_user"]["first_name"], "OnlyName")
        
        print("✅ Пользователь без username: имя СОХРАНЯЕТСЯ")

if __name__ == '__main__':
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ПРИВАТНОСТИ ПОЛЬЗОВАТЕЛЕЙ")
    print("=" * 60)
    unittest.main(verbosity=2)
