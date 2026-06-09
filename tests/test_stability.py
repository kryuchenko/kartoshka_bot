"""Тесты веток стабильности: атомарные записи, guard'ы callback'ов,
живучесть scheduler.run и супервизора фоновых тасков, recruit-хендлер."""
import asyncio
import json
import logging
import os
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kartoshka import storage
from kartoshka.handlers import register_handlers
from kartoshka.scheduler import Scheduler
from kartoshka.state import AppState


class RecordingDP:
    def __init__(self):
        self.messages = []
        self.callbacks = []

    def message(self, *a, **kw):
        return lambda fn: self.messages.append(fn) or fn

    def callback_query(self, *a, **kw):
        return lambda fn: self.callbacks.append(fn) or fn


def _make_state():
    bot = AsyncMock()
    scheduler = MagicMock()
    scheduler.pending_memes = {}
    scheduler.save_moderation = MagicMock()
    scheduler.schedule = AsyncMock()
    scheduler.resolve = MagicMock()
    return AppState(bot=bot, scheduler=scheduler)


def _editor_callback(data, user_id=111):
    cb = MagicMock()
    cb.data = data
    cb.from_user = SimpleNamespace(id=user_id)
    cb.message = SimpleNamespace(chat=SimpleNamespace(id=1), message_id=10)
    cb.answer = AsyncMock()
    return cb


def _capture_crypto_callback(state):
    dp = RecordingDP()
    register_handlers(dp, state)
    # callbacks: [0] choice_*, [1] crypto_callback, [2] noop, [3] crypto_join
    return dp.callbacks[1], dp.callbacks[3]


# ===== storage.atomic_write_json =====

def test_atomic_write_no_tmp_leftover_on_failure(tmp_path):
    """json.dump падает на середине → tmp-файл подчищен, исключение проброшено."""
    p = tmp_path / "x.json"
    with pytest.raises(TypeError):
        storage.atomic_write_json(str(p), {"bad": {1, 2, 3}})  # set несериализуем
    assert os.listdir(tmp_path) == []  # ни x.json, ни *.tmp


def test_load_candidates_corrupt_logs(tmp_path, monkeypatch, caplog):
    f = tmp_path / "candidates.json"
    f.write_text("{broken")
    monkeypatch.setattr(storage, "CANDIDATES_FILE", str(f))
    with caplog.at_level(logging.ERROR):
        assert storage.load_candidates() == []
    assert "Ошибка при загрузке кандидатов" in caplog.text


def test_save_candidates_error_logs(monkeypatch, caplog):
    monkeypatch.setattr(storage, "CANDIDATES_FILE", "/nonexistent_dir_xyz/c.json")
    with caplog.at_level(logging.ERROR):
        storage.save_candidates([{"id": 1}])
    assert "Ошибка при сохранении кандидатов" in caplog.text


def test_atomic_write_cleanup_unlink_failure(tmp_path):
    """Если и зачистка tmp не удалась — исходное исключение всё равно пробрасывается."""
    p = tmp_path / "x.json"
    with patch("kartoshka.storage.os.unlink", side_effect=OSError("busy")):
        with pytest.raises(TypeError):
            storage.atomic_write_json(str(p), {"bad": {1, 2, 3}})


# ===== moderation: guard'ы callback =====


@pytest.mark.asyncio
async def test_crypto_callback_rejects_non_editor():
    state = _make_state()
    crypto_callback, _ = _capture_crypto_callback(state)
    cb = _editor_callback("approve_1", user_id=999)  # не входит в EDITOR_IDS
    await crypto_callback(cb)
    cb.answer.assert_awaited_once_with("Вы не модератор.", show_alert=True)
    state.scheduler.save_moderation.assert_not_called()

@pytest.mark.asyncio
async def test_crypto_callback_malformed_meme_id():
    state = _make_state()
    crypto_callback, _ = _capture_crypto_callback(state)
    cb = _editor_callback("approve_abc")
    await crypto_callback(cb)
    cb.answer.assert_awaited_once_with("Некорректный запрос.")
    state.scheduler.save_moderation.assert_not_called()


@pytest.mark.asyncio
async def test_crypto_callback_answer_failure_does_not_break_vote(caplog):
    """callback.answer упал (stale query) → голос всё равно учтён и финализирован."""
    from kartoshka.models import Meme
    state = _make_state()
    crypto_callback, _ = _capture_crypto_callback(state)
    meme = Meme(meme_id=1, user_id=7, publish_choice="potato", content=MagicMock(content_type="text", text="x"))
    state.scheduler.pending_memes[1] = meme

    cb = _editor_callback("approve_1")
    cb.answer = AsyncMock(side_effect=Exception("query is too old"))
    with patch("kartoshka.handlers.moderation.save_user_data"), \
         caplog.at_level(logging.ERROR):
        await crypto_callback(cb)

    assert "Не удалось ответить на callback" in caplog.text
    state.scheduler.schedule.assert_awaited_once()  # финализация прошла


@pytest.mark.asyncio
async def test_crypto_callback_edit_failure_still_finalizes(caplog):
    """edit_message_reply_markup упал → мем не зависает: финализация выполняется."""
    from kartoshka.models import Meme
    state = _make_state()
    state.bot.edit_message_reply_markup = AsyncMock(side_effect=Exception("message too old"))
    crypto_callback, _ = _capture_crypto_callback(state)
    meme = Meme(meme_id=2, user_id=7, publish_choice="potato", content=MagicMock(content_type="text", text="x"))
    meme.user_messages.append((7, 100))
    state.scheduler.pending_memes[2] = meme

    cb = _editor_callback("approve_2")
    with patch("kartoshka.handlers.moderation.save_user_data"), \
         caplog.at_level(logging.ERROR):
        await crypto_callback(cb)

    assert "Не удалось обновить клавиатуры" in caplog.text
    state.scheduler.schedule.assert_awaited_once()
    state.scheduler.resolve.assert_called_once_with(2)


# ===== scheduler: битые записи и живучесть run() =====

def _isolated_scheduler(tmp_path, monkeypatch, **kw):
    monkeypatch.setattr(Scheduler, "MODERATION_FILE", str(tmp_path / "mod.json"))
    monkeypatch.setattr(Scheduler, "PUBLICATION_FILE", str(tmp_path / "pub.json"))
    return Scheduler(post_frequency_minutes=1, **kw)


def test_load_publication_skips_corrupt_entries(tmp_path, monkeypatch, caplog):
    pub = tmp_path / "pub.json"
    good_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    pub.write_text(json.dumps({
        "last_published_time": datetime.now(timezone.utc).isoformat(),
        "queue": [
            {"scheduled_time": good_time, "meme": {"meme_id": 1}},
            {"scheduled_time": "не-дата", "meme": {"meme_id": 2}},
            {"meme": {"meme_id": 3}},  # нет scheduled_time
        ],
    }))
    with caplog.at_level(logging.ERROR):
        s = _isolated_scheduler(tmp_path, monkeypatch)
    assert [e["meme"]["meme_id"] for e in s.scheduled_posts] == [1]
    assert caplog.text.count("битым scheduled_time") == 2


@pytest.mark.asyncio
async def test_scheduler_run_survives_iteration_error(tmp_path, monkeypatch, caplog):
    """Битая запись в очереди (Meme.from_dict падает) не убивает цикл."""
    s = _isolated_scheduler(tmp_path, monkeypatch)
    s.scheduled_posts = [{
        "scheduled_time": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        "meme": {},  # нет обязательных полей → KeyError в from_dict
    }]
    with caplog.at_level(logging.ERROR):
        task = asyncio.create_task(s.run())
        await asyncio.sleep(0.05)
        assert not task.done()  # цикл жив, спит после ошибки
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    assert "Ошибка в цикле планировщика" in caplog.text


# ===== main: супервизор фоновых тасков =====

@pytest.mark.asyncio
async def test_supervise_restarts_crashed_task(caplog):
    from kartoshka.main import _supervise

    calls = []

    async def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise ValueError("boom")
        await asyncio.Event().wait()  # вторая итерация: живём

    real_sleep = asyncio.sleep  # патч глушит sleep(5) супервизора, но нам самим нужен yield
    with patch("asyncio.sleep", AsyncMock()), caplog.at_level(logging.ERROR):
        task = asyncio.create_task(_supervise("flaky", flaky))
        for _ in range(10):
            if len(calls) >= 2:
                break
            await real_sleep(0)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    assert len(calls) == 2  # упал и был перезапущен
    assert "Фоновый таск flaky упал" in caplog.text


@pytest.mark.asyncio
async def test_supervise_propagates_cancel():
    from kartoshka.main import _supervise

    started = asyncio.Event()

    async def forever():
        started.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(_supervise("forever", forever))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


# ===== config: валидация EDITOR_IDS =====

def test_config_editor_ids_validation(monkeypatch):
    import importlib

    from kartoshka import config as config_module

    monkeypatch.setenv("EDITOR_IDS", "111,abc")
    with pytest.raises(ValueError, match="EDITOR_IDS"):
        importlib.reload(config_module)

    monkeypatch.setenv("EDITOR_IDS", " , ")
    with pytest.raises(ValueError, match="ни одного"):
        importlib.reload(config_module)

    # восстанавливаем валидный конфиг для остальных тестов
    monkeypatch.setenv("EDITOR_IDS", "111,222,333")
    importlib.reload(config_module)
    assert config_module.EDITOR_IDS == [111, 222, 333]


# ===== recruit-хендлер =====

@pytest.mark.asyncio
async def test_recruit_elections_closed():
    state = _make_state()
    _, crypto_join = _capture_crypto_callback(state)
    cb = _editor_callback("crypto_join", user_id=777)
    await crypto_join(cb)
    cb.answer.assert_awaited_once()
    assert "завершены" in cb.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_recruit_flow_when_open(tmp_path, monkeypatch):
    from kartoshka.handlers import recruit as recruit_module

    monkeypatch.setattr(recruit_module, "ELECTIONS_OPEN", True)
    monkeypatch.setattr(storage, "CANDIDATES_FILE", str(tmp_path / "candidates.json"))
    state = _make_state()
    _, crypto_join = _capture_crypto_callback(state)

    # действующий редактор — отбой
    cb_editor = _editor_callback("crypto_join", user_id=111)
    cb_editor.from_user = SimpleNamespace(id=111, username="ed", first_name="Ed")
    await crypto_join(cb_editor)
    assert "уже криптоселектарх" in cb_editor.answer.await_args.args[0]

    # новый кандидат
    cb_new = _editor_callback("crypto_join", user_id=777)
    cb_new.from_user = SimpleNamespace(id=777, username="nu", first_name="Nu")
    await crypto_join(cb_new)
    assert "в списке кандидатов!" in cb_new.answer.await_args.args[0]

    # повторный отклик — идемпотентно
    cb_again = _editor_callback("crypto_join", user_id=777)
    cb_again.from_user = SimpleNamespace(id=777, username="nu2", first_name="Nu")
    await crypto_join(cb_again)
    assert "уже в списке" in cb_again.answer.await_args.args[0]

    cands = storage.load_candidates()
    assert len(cands) == 1 and cands[0]["username"] == "nu2"
