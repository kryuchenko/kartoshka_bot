import html
import math
import random
from datetime import datetime, timezone
from typing import Optional

from kartoshka import config
from kartoshka.constants import METALS_AND_TOXINS
from kartoshka.message_snapshot import MessageSnapshot


class Meme:
    def __init__(
        self,
        meme_id: int,
        user_id: Optional[int],
        publish_choice: str,
        content,
    ):
        self.meme_id = meme_id
        self.user_id = user_id
        self.publish_choice = publish_choice
        # Нормализуем любой Message-like объект в лёгкий snapshot.
        # Production-код передаёт уже готовый MessageSnapshot; auto-convert
        # сохраняет обратную совместимость со старыми тестами / внешними caller'ами.
        self.content = content if isinstance(content, MessageSnapshot) else MessageSnapshot.from_message(content)
        self.votes = {}
        self.mod_messages = []
        self.user_messages = []
        self.finalized = False
        self.created_time = datetime.now(timezone.utc)

    def add_vote(self, crypto_id: int, vote: str) -> Optional[str]:
        key = str(crypto_id)
        prev_vote = self.votes.get(key)
        self.votes[key] = vote
        return prev_vote

    def count_votes(self, vote_type: str) -> int:
        if vote_type == "approve":
            return sum(1 for v in self.votes.values() if v in ("approve", "urgent"))
        return sum(1 for v in self.votes.values() if v == vote_type)

    def is_approved(self) -> bool:
        return self.count_votes("approve") >= config.VOTES_TO_APPROVE

    def is_urgent(self) -> bool:
        urgent_count = sum(1 for v in self.votes.values() if v == "urgent")
        urgent_threshold = max(1, math.ceil(config.VOTES_TO_APPROVE * 0.51))
        return urgent_count >= urgent_threshold

    def is_rejected(self) -> bool:
        return self.count_votes("reject") >= config.VOTES_TO_REJECT

    def get_vote_summary(self) -> str:
        approve_count = sum(1 for v in self.votes.values() if v == "approve")
        urgent_count = sum(1 for v in self.votes.values() if v == "urgent")
        reject_count = sum(1 for v in self.votes.values() if v == "reject")
        return f"(✅ {approve_count} | ⚡ {urgent_count} | ❌ {reject_count})"

    def get_caption(self) -> str:
        # parse_mode=HTML ⇒ экранируем всё пользовательское.
        raw_text = self.content.text or self.content.caption or ""
        user_text = html.escape(raw_text)
        if self.publish_choice == "user":
            username = self.content.from_user_username
            first_name = self.content.from_user_first_name
            if username:
                prefix = f"Мем от пользователя @{html.escape(username)}"
            elif first_name:
                prefix = f"Мем от пользователя {html.escape(first_name)}"
            else:
                prefix = "Мем от пользователя [ДАННЫЕ УДАЛЕНЫ]"
        else:
            random_metal = random.choice(METALS_AND_TOXINS)
            plain_prefix = f"Мем от Анонимной {random_metal} Картошки"
            prefix = f"<tg-spoiler>{plain_prefix}</tg-spoiler>"

        return f"{prefix}\n\n{user_text}" if user_text else f"{prefix}"

    def to_dict(self) -> dict:
        content = self.content.to_dict()
        # Анонимные мемы: не сохраняем данные об авторе на диск.
        if self.publish_choice == "potato":
            content.pop("from_user", None)

        meme_dict = {
            "meme_id": self.meme_id,
            "publish_choice": self.publish_choice,
            "content": content,
            "created_time": self.created_time.isoformat(),
            "votes": self.votes,
        }
        if self.publish_choice != "potato":
            meme_dict["user_id"] = self.user_id
        return meme_dict

    def to_publication_dict(self) -> dict:
        content = self.content.to_dict()
        if self.publish_choice == "potato":
            content.pop("from_user", None)

        meme_dict = {
            "meme_id": self.meme_id,
            "publish_choice": self.publish_choice,
            "content": content,
            "created_time": self.created_time.isoformat(),
        }
        if self.publish_choice != "potato":
            meme_dict["user_id"] = self.user_id
        return meme_dict

    @classmethod
    def from_dict(cls, d: dict) -> "Meme":
        content = MessageSnapshot.from_dict(d["content"])
        meme = cls(
            meme_id=d["meme_id"],
            user_id=d.get("user_id"),
            publish_choice=d["publish_choice"],
            content=content,
        )
        meme.created_time = datetime.fromisoformat(d["created_time"])
        meme.votes = d.get("votes", {})
        return meme
