"""Shared pytest setup: env + изоляция JSON-storage от боевых файлов."""
import os

# env-переменные ставим ДО любого импорта kartoshka.* — config валидирует их
# на module load. Порядок загрузки тестовых модулей алфавитный, поэтому
# без conftest один файл мог перехватить env до другого.
os.environ.setdefault("BOT_TOKEN", "123:dummy")
os.environ.setdefault("EDITOR_IDS", "111,222,333")
os.environ.setdefault("PUBLISH_CHAT_ID", "12345")
os.environ.setdefault("BOT_NAME", "TestBot")
os.environ.setdefault("POST_FREQUENCY_MINUTES", "60")
os.environ.setdefault("CRYPTOSELECTARCHY", "true")
os.environ.setdefault("VOTES_TO_APPROVE", "2")
os.environ.setdefault("VOTES_TO_REJECT", "2")

from unittest.mock import patch as _patch

import pytest


@pytest.fixture(autouse=True)
def _stable_config():
    """Защита от гонок env: закрепляем config-значения на время теста.

    - CI workflow ставит VOTES_TO_*=3, локальный env из conftest — 2.
    - Некоторые тесты патчат importlib.reload(config), что сдвигает значения.
    Фиксируем stable-набор для всех тестов; кому надо другое — патчит поверх.
    """
    with _patch("kartoshka.config.VOTES_TO_APPROVE", 2), \
         _patch("kartoshka.config.VOTES_TO_REJECT", 2), \
         _patch("kartoshka.config.CRYPTOSELECTARCHY", False):
        yield


@pytest.fixture(autouse=True)
def isolate_json_storage(tmp_path, monkeypatch):
    """Все JSON-файлы хранилища redirect'ятся в tmp_path на время теста.

    Без этого pytest на продакшн-машине перезаписал бы meme_counter.json и
    moderation_queue.json в cwd, разрушая состояние бота.
    """
    counter = str(tmp_path / "meme_counter.json")
    user_data = str(tmp_path / "user_data.json")
    moderation = str(tmp_path / "moderation_queue.json")
    publication = str(tmp_path / "publication_queue.json")

    # storage.py импортирует имена на уровне модуля
    monkeypatch.setattr("kartoshka.storage.COUNTER_FILE", counter)
    monkeypatch.setattr("kartoshka.storage.USER_DATA_FILE", user_data)

    # Scheduler использует class attrs
    monkeypatch.setattr("kartoshka.scheduler.Scheduler.MODERATION_FILE", moderation)
    monkeypatch.setattr("kartoshka.scheduler.Scheduler.PUBLICATION_FILE", publication)
