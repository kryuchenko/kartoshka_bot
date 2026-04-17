from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

if TYPE_CHECKING:
    from aiogram import Bot

    from kartoshka.scheduler import Scheduler


PUBLISH_CHOICE_TTL = timedelta(hours=1)


@dataclass
class AppState:
    """Shared runtime state, создаётся в main() и передаётся handlers/Scheduler."""

    bot: "Bot"
    scheduler: "Scheduler"
    meme_counter: int = 0
    user_data: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # user_id -> (choice, expires_at). Запись живёт PUBLISH_CHOICE_TTL после /start.
    user_publish_choice: Dict[int, Tuple[str, datetime]] = field(default_factory=dict)

    def set_publish_choice(self, user_id: int, choice: str) -> None:
        """Сохраняет выбор пользователя на PUBLISH_CHOICE_TTL."""
        self.user_publish_choice[user_id] = (
            choice,
            datetime.now(timezone.utc) + PUBLISH_CHOICE_TTL,
        )

    def get_publish_choice(self, user_id: int) -> Optional[str]:
        """Возвращает активный выбор или None (с lazy-eviction истёкшего)."""
        entry = self.user_publish_choice.get(user_id)
        if entry is None:
            return None
        choice, expires_at = entry
        if expires_at < datetime.now(timezone.utc):
            self.user_publish_choice.pop(user_id, None)
            return None
        return choice

    def expire_old_choices(self) -> int:
        """Sweep истёкших записей. Возвращает сколько удалено."""
        now = datetime.now(timezone.utc)
        expired = [
            uid for uid, (_, exp) in self.user_publish_choice.items() if exp < now
        ]
        for uid in expired:
            del self.user_publish_choice[uid]
        return len(expired)
