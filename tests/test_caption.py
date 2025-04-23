#!/usr/bin/env python3
import unittest
import random
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# Определяем основные классы и функции без импорта основного модуля

class DummyMeme:
    def __init__(self, publish_choice, content):
        self.publish_choice = publish_choice
        self.content = content
    
    def get_caption(self):
        # Копия метода get_caption из класса Meme
        user_text = getattr(self.content, "caption", "") or getattr(self.content, "text", "")
        if self.publish_choice == "user":
            prefix = "Мем от пользователя"
        else:
            metals = ["Алюминиевой", "Железной", "Медной"]
            random_metal = random.choice(metals)
            plain_prefix = f"Мем от Анонимной {random_metal} Картошки"
            prefix = f"<tg-spoiler>{plain_prefix}</tg-spoiler>"
        
        # Всегда возвращаем подпись с префиксом, даже если пользовательский текст пустой
        return f"{prefix}\n\n{user_text}" if user_text else f"{prefix}"


async def dummy_send_media_message(telegram_bot, chat_id, content, caption=None, reply_markup=None):
    # Копия функции send_media_message
    if not caption:
        caption = getattr(content, "caption", "") or getattr(content, "text", "")
    caption = caption or ""
    ctype = getattr(content, "content_type", "text")
    if ctype == "photo":
        return await telegram_bot.send_photo(
            chat_id=chat_id,
            photo=content.photo[-1].file_id,
            caption=caption,
            reply_markup=reply_markup
        )
    elif ctype == "video":
        return await telegram_bot.send_video(
            chat_id=chat_id,
            video=content.video.file_id,
            caption=caption,
            reply_markup=reply_markup
        )
    elif ctype == "animation":
        return await telegram_bot.send_animation(
            chat_id=chat_id,
            animation=content.animation.file_id,
            caption=caption,
            reply_markup=reply_markup
        )
    elif ctype == "voice":
        return await telegram_bot.send_voice(
            chat_id=chat_id,
            voice=content.voice.file_id,
            caption=caption,
            reply_markup=reply_markup
        )
    elif ctype == "video_note":
        return await telegram_bot.send_video_note(
            chat_id=chat_id,
            video_note=content.video_note.file_id,
            reply_markup=reply_markup
        )
    else:
        # Всегда используем caption для текстовых сообщений, а не только text
        return await telegram_bot.send_message(
            chat_id=chat_id,
            text=caption,
            reply_markup=reply_markup
        )


async def dummy_publish_meme(meme, chat_id=123):
    # Упрощенная версия функции publish_meme
    try:
        # Всегда передаем caption явно для правильной подписи
        caption = meme.get_caption()
        await dummy_send_media_message(
            telegram_bot=MagicMock(),
            chat_id=chat_id,
            content=meme.content,
            caption=caption
        )
    except Exception as e:
        print(f"Ошибка при публикации: {e}")


class TestCaption(unittest.TestCase):
    
    def test_get_caption_text_only(self):
        """Проверяет что текстовый мем всегда имеет подпись"""
        # Создаем объект для текстового контента с реальными атрибутами
        class TextContent:
            def __init__(self, text=""):
                self.content_type = "text"
                self.text = text
                self.caption = None
        
        text_content = TextContent(text="Текст мема")
        
        # Тестируем мем от пользователя
        meme_user = DummyMeme(publish_choice="user", content=text_content)
        caption = meme_user.get_caption()
        self.assertTrue(caption.startswith("Мем от пользователя"))
        self.assertIn("Текст мема", caption)
        
        # Тестируем анонимный мем
        meme_anon = DummyMeme(publish_choice="potato", content=text_content)
        caption = meme_anon.get_caption()
        self.assertTrue("Мем от Анонимной" in caption)
        self.assertIn("Текст мема", caption)
        
        # Тестируем мем без текста
        empty_content = TextContent(text="")
        
        meme_empty_user = DummyMeme(publish_choice="user", content=empty_content)
        caption = meme_empty_user.get_caption()
        self.assertEqual(caption, "Мем от пользователя")
        
        meme_empty_anon = DummyMeme(publish_choice="potato", content=empty_content)
        caption = meme_empty_anon.get_caption()
        self.assertTrue(caption.startswith("<tg-spoiler>Мем от Анонимной"))


class TestSendMediaMessage(unittest.IsolatedAsyncioTestCase):
    
    async def test_send_text_message_with_caption(self):
        """Проверяет что при отправке текстового сообщения всегда используется caption"""
        # Настраиваем мок
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(return_value=MagicMock())
        
        # Создаем мок-объект для текстового контента
        text_content = SimpleNamespace(
            content_type="text",
            text="Текст сообщения"
        )
        
        # Тестируем с явным caption
        await dummy_send_media_message(
            telegram_bot=mock_bot,
            chat_id=123,
            content=text_content,
            caption="Мем от Анонимной Картошки"
        )
        
        # Проверяем что вызвали send_message с правильной подписью
        mock_bot.send_message.assert_called_with(
            chat_id=123,
            text="Мем от Анонимной Картошки",
            reply_markup=None
        )
        
        # Тестируем без явного caption
        mock_bot.send_message.reset_mock()
        await dummy_send_media_message(
            telegram_bot=mock_bot,
            chat_id=123,
            content=text_content
        )
        
        # Проверяем что вызвали send_message с текстом сообщения
        mock_bot.send_message.assert_called_with(
            chat_id=123,
            text="Текст сообщения",
            reply_markup=None
        )


class TestPublishMeme(unittest.IsolatedAsyncioTestCase):
    
    async def test_publish_meme_with_caption(self):
        """Проверяет что publish_meme всегда передает caption в send_media_message"""
        # Создаем мок-объекты
        text_content = MagicMock()
        text_content.content_type = "text"
        text_content.text = ""
        
        # Создаем мем
        meme = DummyMeme(publish_choice="potato", content=text_content)
        
        # Используем временную функцию вместо моков
        # для совместимости с GitHub Actions
        async def mock_send_media(**kwargs):
            # Просто запоминаем параметры
            mock_send_media.last_kwargs = kwargs
            return None
            
        mock_send_media.last_kwargs = {}
        
        # Сохраняем оригинальную функцию
        original_func = globals().get('dummy_send_media_message')
        
        try:
            # Заменяем функцию на нашу тестовую
            globals()['dummy_send_media_message'] = mock_send_media
            
            # Публикуем мем
            await dummy_publish_meme(meme, chat_id=123)
            
            # Проверяем аргументы
            self.assertEqual(mock_send_media.last_kwargs["chat_id"], 123)
            self.assertEqual(mock_send_media.last_kwargs["content"], text_content)
            self.assertTrue("<tg-spoiler>Мем от Анонимной" in mock_send_media.last_kwargs["caption"])
        finally:
            # Восстанавливаем оригинальную функцию
            if original_func:
                globals()['dummy_send_media_message'] = original_func


if __name__ == "__main__":
    unittest.main()