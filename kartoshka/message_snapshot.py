"""Лёгкий immutable-снимок aiogram.Message.

Бот использует из Message ~11 примитивных полей, но aiogram.Message — pydantic-модель
со 109 полями и вложенными моделями (User/Chat/Photo/...). Держать его в pending_memes
на часы-дни = 11 KB/мем оверхеда против 1 KB для чистого dataclass'а.

Формат JSON на диске намеренно совместим со старым serialize_message форматом:
  {"content_type": "photo", "photo": [{"file_id": "..."}], "caption": "...",
   "from_user": {"id": 1, "username": "x", "first_name": "X"}}
чтобы существующие moderation_queue.json на проде читались без миграции.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class MessageSnapshot:
    content_type: str
    text: Optional[str] = None
    caption: Optional[str] = None
    photo_file_id: Optional[str] = None
    video_file_id: Optional[str] = None
    animation_file_id: Optional[str] = None
    voice_file_id: Optional[str] = None
    video_note_file_id: Optional[str] = None
    from_user_id: Optional[int] = None
    from_user_username: Optional[str] = None
    from_user_first_name: Optional[str] = None

    @classmethod
    def from_message(cls, message) -> "MessageSnapshot":
        """Выжимает нужные поля из входящего aiogram.types.Message."""
        ct = getattr(message, "content_type", "text")
        kwargs = {"content_type": ct}

        if ct == "text":
            kwargs["text"] = getattr(message, "text", None)
        elif ct == "photo":
            photo = getattr(message, "photo", None)
            if photo:
                try:
                    kwargs["photo_file_id"] = photo[-1].file_id
                except (AttributeError, IndexError, TypeError):
                    pass
            kwargs["caption"] = getattr(message, "caption", None)
        elif ct == "video":
            video = getattr(message, "video", None)
            if video is not None:
                kwargs["video_file_id"] = getattr(video, "file_id", None)
            kwargs["caption"] = getattr(message, "caption", None)
        elif ct == "animation":
            animation = getattr(message, "animation", None)
            if animation is not None:
                kwargs["animation_file_id"] = getattr(animation, "file_id", None)
            kwargs["caption"] = getattr(message, "caption", None)
        elif ct == "voice":
            voice = getattr(message, "voice", None)
            if voice is not None:
                kwargs["voice_file_id"] = getattr(voice, "file_id", None)
            kwargs["caption"] = getattr(message, "caption", None)
        elif ct == "video_note":
            vn = getattr(message, "video_note", None)
            if vn is not None:
                kwargs["video_note_file_id"] = getattr(vn, "file_id", None)
        else:
            kwargs["text"] = getattr(message, "text", None)

        from_user = getattr(message, "from_user", None)
        if from_user:
            kwargs["from_user_id"] = getattr(from_user, "id", None)
            kwargs["from_user_username"] = getattr(from_user, "username", None)
            kwargs["from_user_first_name"] = getattr(from_user, "first_name", None)

        return cls(**kwargs)

    def to_dict(self) -> dict:
        """Сериализация в старый nested-формат (обратная совместимость с диском)."""
        d: dict = {"content_type": self.content_type}
        if self.content_type == "text":
            d["text"] = self.text or ""
        elif self.content_type == "photo":
            d["photo"] = [{"file_id": self.photo_file_id}] if self.photo_file_id else []
            d["caption"] = self.caption
        elif self.content_type == "video":
            d["video"] = {"file_id": self.video_file_id or ""}
            d["caption"] = self.caption
        elif self.content_type == "animation":
            d["animation"] = {"file_id": self.animation_file_id or ""}
            d["caption"] = self.caption
        elif self.content_type == "voice":
            d["voice"] = {"file_id": self.voice_file_id or ""}
            d["caption"] = self.caption
        elif self.content_type == "video_note":
            d["video_note"] = {"file_id": self.video_note_file_id or ""}
        else:
            d["text"] = self.text or ""

        if self.from_user_id is not None:
            d["from_user"] = {
                "id": self.from_user_id,
                "username": self.from_user_username,
                "first_name": self.from_user_first_name,
            }
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "MessageSnapshot":
        """Читает старый nested-формат (то, что хранится в moderation_queue.json)."""
        ct = d.get("content_type", "text")
        kwargs = {"content_type": ct}

        if ct == "photo":
            photo = d.get("photo") or []
            if photo:
                try:
                    kwargs["photo_file_id"] = photo[-1]["file_id"]
                except (KeyError, IndexError, TypeError):
                    pass
            kwargs["caption"] = d.get("caption")
        elif ct == "video":
            kwargs["video_file_id"] = (d.get("video") or {}).get("file_id")
            kwargs["caption"] = d.get("caption")
        elif ct == "animation":
            kwargs["animation_file_id"] = (d.get("animation") or {}).get("file_id")
            kwargs["caption"] = d.get("caption")
        elif ct == "voice":
            kwargs["voice_file_id"] = (d.get("voice") or {}).get("file_id")
            kwargs["caption"] = d.get("caption")
        elif ct == "video_note":
            kwargs["video_note_file_id"] = (d.get("video_note") or {}).get("file_id")
        else:
            kwargs["text"] = d.get("text")

        from_user = d.get("from_user")
        if from_user:
            kwargs["from_user_id"] = from_user.get("id")
            kwargs["from_user_username"] = from_user.get("username")
            kwargs["from_user_first_name"] = from_user.get("first_name")

        return cls(**kwargs)
