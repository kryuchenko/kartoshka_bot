#!/usr/bin/env python3
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import random
from types import SimpleNamespace

class DummyMeme:
    def __init__(self, user_id=123):
        self.user_id = user_id
        self.user_messages = [(user_id, 456)]
        self.votes = {}
    
    def get_vote_summary(self):
        approve_count = sum(1 for v in self.votes.values() if v == "approve")
        urgent_count = sum(1 for v in self.votes.values() if v == "urgent")
        reject_count = sum(1 for v in self.votes.values() if v == "reject")
        return f"(✅ {approve_count} | ⚡ {urgent_count} | ❌ {reject_count})"
    
    def add_vote(self, crypto_id, vote):
        key = str(crypto_id)
        prev_vote = self.votes.get(key)
        self.votes[key] = vote
        return prev_vote


async def update_user_messages_with_status(meme, final_resolution=None):
    """Копия функции update_user_messages_with_status для тестирования"""
    if meme.user_id is None or not meme.user_messages:
        return
    
    vote_summary = meme.get_vote_summary()
    
    if final_resolution:
        status_text = f"{final_resolution} {vote_summary}"
    else:
        status_text = f"Голосование: {vote_summary}"
    
    # Здесь в реальном коде создается клавиатура и происходит обновление сообщений
    # Для теста просто возвращаем текст кнопки
    return status_text


class TestUserWidget(unittest.IsolatedAsyncioTestCase):
    
    async def test_vote_updates(self):
        """Проверяет обновление статуса голосования в виджете пользователя"""
        meme = DummyMeme()
        
        # Начальный статус - пустое голосование
        status = await update_user_messages_with_status(meme)
        self.assertEqual(status, "Голосование: (✅ 0 | ⚡ 0 | ❌ 0)")
        
        # Добавляем голос "за"
        meme.add_vote(1, "approve")
        status = await update_user_messages_with_status(meme)
        self.assertEqual(status, "Голосование: (✅ 1 | ⚡ 0 | ❌ 0)")
        
        # Добавляем голос "срочно"
        meme.add_vote(2, "urgent")
        status = await update_user_messages_with_status(meme)
        self.assertEqual(status, "Голосование: (✅ 1 | ⚡ 1 | ❌ 0)")
        
        # Добавляем голос "против"
        meme.add_vote(3, "reject")
        status = await update_user_messages_with_status(meme)
        self.assertEqual(status, "Голосование: (✅ 1 | ⚡ 1 | ❌ 1)")
        
        # Меняем голос с "за" на "против"
        meme.add_vote(1, "reject")
        status = await update_user_messages_with_status(meme)
        self.assertEqual(status, "Голосование: (✅ 0 | ⚡ 1 | ❌ 2)")
        
        # Финальное решение
        status = await update_user_messages_with_status(meme, "❌ Отклонён")
        self.assertEqual(status, "❌ Отклонён (✅ 0 | ⚡ 1 | ❌ 2)")


if __name__ == "__main__":
    unittest.main()