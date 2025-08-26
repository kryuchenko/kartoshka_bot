#!/usr/bin/env python3
"""Тест для проверки приватности данных пользователей"""

import unittest
from unittest.mock import MagicMock
import sys
import os

# Добавляем родительский каталог в путь для импорта модуля
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Импорты из тестового модуля, который уже корректно настроен
from tests.test_kartoshka_bot import Meme, DummyUser, TestMessage

class TestPrivacy(unittest.TestCase):
    def test_user_meme_shows_username(self):
        """Неанонимный мем показывает username"""
        user = DummyUser(username="publicuser", id=123)
        msg = TestMessage(text="Публичный мем", from_user=user)
        meme = Meme(1, 123, "user", msg)
        
        # Получаем caption
        caption = meme.get_caption()
        print(f"\nНеанонимный caption: {caption}")
        
        # Проверяем что username есть
        self.assertIn("@publicuser", caption)
        
        # Проверяем сериализацию
        meme_dict = meme.to_dict()
        print(f"Сериализация неанонимного: from_user в content = {'from_user' in meme_dict['content']}")
        
        # Данные пользователя должны сохраняться
        self.assertIn("from_user", meme_dict["content"])
        self.assertEqual(meme_dict["content"]["from_user"]["username"], "publicuser")
        self.assertIn("user_id", meme_dict)
        
        print("✅ Неанонимный мем: username ОТОБРАЖАЕТСЯ и СОХРАНЯЕТСЯ")
        
    def test_anonymous_meme_hides_username(self):
        """Анонимный мем скрывает username"""
        user = DummyUser(username="secretuser", id=456)
        msg = TestMessage(text="Секретный мем", from_user=user)
        meme = Meme(2, 456, "potato", msg)
        
        # Получаем caption
        caption = meme.get_caption()
        print(f"\nАнонимный caption: {caption}")
        
        # Проверяем что username НЕТ
        self.assertNotIn("@secretuser", caption)
        self.assertIn("Картошки</tg-spoiler>", caption)
        
        # Проверяем сериализацию
        meme_dict = meme.to_dict()
        print(f"Сериализация анонимного: from_user в content = {'from_user' in meme_dict['content']}")
        print(f"user_id в meme_dict = {'user_id' in meme_dict}")
        
        # Данные пользователя НЕ должны сохраняться
        self.assertNotIn("from_user", meme_dict["content"])
        self.assertNotIn("user_id", meme_dict)
        
        print("✅ Анонимный мем: username НЕ ОТОБРАЖАЕТСЯ и НЕ СОХРАНЯЕТСЯ")

if __name__ == "__main__":
    print("="*60)
    print("ТЕСТ ПРИВАТНОСТИ ДАННЫХ")
    print("="*60)
    unittest.main(verbosity=2)
