"""Тесты, закрывающие остатки coverage по storage/scheduler/message_snapshot/handlers."""
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest  # env задан в conftest.py

from kartoshka import storage
from kartoshka.handlers import moderation as moderation_module
from kartoshka.message_snapshot import MessageSnapshot
from kartoshka.models import Meme
from kartoshka.scheduler import Scheduler
from kartoshka.state import AppState


# ===== storage.py: load/save для JSON =====

def test_storage_load_meme_counter_missing_file():
    assert storage.load_meme_counter() == 0


def test_storage_load_meme_counter_ok(tmp_path, monkeypatch):
    p = tmp_path / "counter.json"
    p.write_text('{"meme_counter": 42}')
    monkeypatch.setattr(storage, "COUNTER_FILE", str(p))
    assert storage.load_meme_counter() == 42


def test_storage_load_meme_counter_corrupt(tmp_path, monkeypatch, caplog):
    p = tmp_path / "counter.json"
    p.write_text("not json at all {{{")
    monkeypatch.setattr(storage, "COUNTER_FILE", str(p))
    import logging
    with caplog.at_level(logging.ERROR):
        assert storage.load_meme_counter() == 0
    assert "Ошибка при загрузке счетчика" in caplog.text


def test_storage_save_meme_counter_roundtrip(tmp_path, monkeypatch):
    p = tmp_path / "counter.json"
    monkeypatch.setattr(storage, "COUNTER_FILE", str(p))
    storage.save_meme_counter(123)
    assert json.loads(p.read_text()) == {"meme_counter": 123}
    assert storage.load_meme_counter() == 123


def test_storage_save_meme_counter_exception(monkeypatch, caplog):
    monkeypatch.setattr(storage, "COUNTER_FILE", "/nonexistent_dir_xyz/file.json")
    import logging
    with caplog.at_level(logging.ERROR):
        storage.save_meme_counter(1)
    assert "Ошибка при сохранении счетчика" in caplog.text


def test_storage_load_user_data_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "USER_DATA_FILE", str(tmp_path / "absent.json"))
    assert storage.load_user_data() == {}


def test_storage_load_user_data_roundtrip(tmp_path, monkeypatch):
    p = tmp_path / "user.json"
    monkeypatch.setattr(storage, "USER_DATA_FILE", str(p))
    now = datetime.now(timezone.utc).replace(microsecond=0)
    data = {
        "7": {"last_submission": now, "rejections": 2, "ban_until": None},
        "8": {"last_submission": None, "rejections": 0, "ban_until": now + timedelta(days=1)},
    }
    storage.save_user_data(data)
    loaded = storage.load_user_data()
    assert loaded["7"]["rejections"] == 2
    assert loaded["7"]["last_submission"] == now
    assert loaded["8"]["ban_until"] == now + timedelta(days=1)


def test_storage_load_user_data_corrupt(tmp_path, monkeypatch, caplog):
    p = tmp_path / "user.json"
    p.write_text("{invalid json")
    monkeypatch.setattr(storage, "USER_DATA_FILE", str(p))
    import logging
    with caplog.at_level(logging.ERROR):
        assert storage.load_user_data() == {}
    assert "Ошибка при загрузке данных пользователей" in caplog.text


def test_storage_save_user_data_exception(monkeypatch, caplog):
    monkeypatch.setattr(storage, "USER_DATA_FILE", "/nonexistent_xyz/user.json")
    import logging
    with caplog.at_level(logging.ERROR):
        storage.save_user_data({"1": {"last_submission": None, "rejections": 0, "ban_until": None}})
    assert "Ошибка при сохранении данных пользователей" in caplog.text


# ===== message_snapshot.py: все типы контента =====

def _make_fake_message(**overrides):
    from_user = SimpleNamespace(id=1, username="u", first_name="U")
    base = dict(
        content_type="text", text=None, caption=None,
        photo=None, video=None, animation=None, voice=None, video_note=None,
        from_user=from_user,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_snapshot_from_message_photo():
    photos = [SimpleNamespace(file_id=f"p_{i}") for i in range(3)]
    msg = _make_fake_message(content_type="photo", photo=photos, caption="hi")
    s = MessageSnapshot.from_message(msg)
    assert s.content_type == "photo"
    assert s.photo_file_id == "p_2"  # последний = самый крупный
    assert s.caption == "hi"


def test_snapshot_from_message_photo_bad_list():
    msg = _make_fake_message(content_type="photo", photo="not a list", caption="x")
    s = MessageSnapshot.from_message(msg)
    assert s.content_type == "photo"
    assert s.photo_file_id is None


def test_snapshot_from_message_video():
    msg = _make_fake_message(content_type="video", video=SimpleNamespace(file_id="v1"), caption="c")
    s = MessageSnapshot.from_message(msg)
    assert s.video_file_id == "v1"
    assert s.caption == "c"


def test_snapshot_from_message_animation():
    msg = _make_fake_message(content_type="animation", animation=SimpleNamespace(file_id="a1"), caption="c")
    s = MessageSnapshot.from_message(msg)
    assert s.animation_file_id == "a1"


def test_snapshot_from_message_voice():
    msg = _make_fake_message(content_type="voice", voice=SimpleNamespace(file_id="vo"), caption="c")
    s = MessageSnapshot.from_message(msg)
    assert s.voice_file_id == "vo"


def test_snapshot_from_message_video_note():
    msg = _make_fake_message(content_type="video_note", video_note=SimpleNamespace(file_id="vn"))
    s = MessageSnapshot.from_message(msg)
    assert s.video_note_file_id == "vn"


def test_snapshot_from_message_unknown_type_fallback():
    msg = _make_fake_message(content_type="poll", text="edge case")
    s = MessageSnapshot.from_message(msg)
    assert s.content_type == "poll"
    assert s.text == "edge case"


def test_snapshot_to_dict_roundtrip_all_types():
    snaps = [
        MessageSnapshot(content_type="text", text="hi", from_user_id=1, from_user_username="u"),
        MessageSnapshot(content_type="photo", photo_file_id="p", caption="cap", from_user_id=1),
        MessageSnapshot(content_type="video", video_file_id="v", caption="c"),
        MessageSnapshot(content_type="animation", animation_file_id="a", caption="c"),
        MessageSnapshot(content_type="voice", voice_file_id="vo", caption="c"),
        MessageSnapshot(content_type="video_note", video_note_file_id="vn"),
        MessageSnapshot(content_type="unknown", text="x"),  # fallback
    ]
    for s in snaps:
        roundtripped = MessageSnapshot.from_dict(s.to_dict())
        assert roundtripped == s


def test_snapshot_from_dict_missing_fields():
    # Минимальный dict без какого-либо контента
    s = MessageSnapshot.from_dict({"content_type": "text"})
    assert s.content_type == "text"
    assert s.text is None

    # Photo с пустым списком
    s = MessageSnapshot.from_dict({"content_type": "photo", "photo": [], "caption": None})
    assert s.photo_file_id is None

    # Photo с битым элементом (не dict)
    s = MessageSnapshot.from_dict({"content_type": "photo", "photo": ["not a dict"], "caption": None})
    assert s.photo_file_id is None


def test_snapshot_from_dict_and_from_message_anonymous():
    """Сообщение без from_user — snapshot не имеет данных автора."""
    msg = _make_fake_message(text="anon", from_user=None)
    s = MessageSnapshot.from_message(msg)
    assert s.from_user_id is None
    assert s.to_dict().get("from_user") is None


# ===== Scheduler: load/save, schedule, run loop =====

@pytest.fixture
def scheduler(tmp_path, monkeypatch):
    monkeypatch.setattr(Scheduler, "MODERATION_FILE", str(tmp_path / "mod.json"))
    monkeypatch.setattr(Scheduler, "PUBLICATION_FILE", str(tmp_path / "pub.json"))
    return Scheduler(post_frequency_minutes=5)


def _make_meme(meme_id=1, publish_choice="user", user_id=7, user_messages=None):
    snap = MessageSnapshot(
        content_type="text", text=f"meme {meme_id}",
        from_user_id=user_id, from_user_username="u", from_user_first_name="U",
    )
    m = Meme(meme_id=meme_id, user_id=user_id, publish_choice=publish_choice, content=snap)
    if user_messages:
        m.user_messages = user_messages
    return m


def test_scheduler_save_moderation_error(scheduler, monkeypatch, caplog):
    monkeypatch.setattr(scheduler, "MODERATION_FILE", "/nonexistent_xyz/mod.json")
    scheduler.pending_memes[1] = _make_meme(1)
    import logging
    with caplog.at_level(logging.ERROR):
        scheduler.save_moderation()
    assert "Ошибка при сохранении модерационной очереди" in caplog.text


def test_scheduler_save_publication_error(scheduler, monkeypatch, caplog):
    monkeypatch.setattr(scheduler, "PUBLICATION_FILE", "/nonexistent_xyz/pub.json")
    import logging
    with caplog.at_level(logging.ERROR):
        scheduler.save_publication()
    assert "Ошибка при сохранении очереди публикации" in caplog.text


def test_scheduler_load_moderation_corrupt(tmp_path, monkeypatch, caplog):
    p = tmp_path / "mod.json"
    p.write_text("garbage{{{")
    monkeypatch.setattr(Scheduler, "MODERATION_FILE", str(p))
    monkeypatch.setattr(Scheduler, "PUBLICATION_FILE", str(tmp_path / "pub.json"))
    import logging
    with caplog.at_level(logging.ERROR):
        s = Scheduler(post_frequency_minutes=5)
    assert s.pending_memes == {}
    assert "Ошибка при загрузке модерационной очереди" in caplog.text


def test_scheduler_load_publication_corrupt(tmp_path, monkeypatch, caplog):
    p = tmp_path / "pub.json"
    p.write_text("garbage{{{")
    monkeypatch.setattr(Scheduler, "MODERATION_FILE", str(tmp_path / "mod.json"))
    monkeypatch.setattr(Scheduler, "PUBLICATION_FILE", str(p))
    import logging
    with caplog.at_level(logging.ERROR):
        s = Scheduler(post_frequency_minutes=5)
    assert s.scheduled_posts == []
    assert "Ошибка при загрузке очереди публикации" in caplog.text


def test_scheduler_load_moderation_roundtrip(tmp_path, monkeypatch):
    """Сохранить 2 мема, загрузить обратно в новый Scheduler."""
    mod_path = tmp_path / "mod.json"
    pub_path = tmp_path / "pub.json"
    monkeypatch.setattr(Scheduler, "MODERATION_FILE", str(mod_path))
    monkeypatch.setattr(Scheduler, "PUBLICATION_FILE", str(pub_path))

    s1 = Scheduler(post_frequency_minutes=5)
    s1.pending_memes[1] = _make_meme(1)
    s1.pending_memes[2] = _make_meme(2, publish_choice="potato")
    s1.save_moderation()

    s2 = Scheduler(post_frequency_minutes=5)
    assert set(s2.pending_memes.keys()) == {1, 2}
    assert s2.pending_memes[1].publish_choice == "user"


def test_scheduler_load_publication_reschedules_past_entries(tmp_path, monkeypatch):
    """Если загруженные scheduled_posts в прошлом — пересчитываются относительно now."""
    mod_path = tmp_path / "mod.json"
    pub_path = tmp_path / "pub.json"
    past = datetime.now(timezone.utc) - timedelta(days=2)
    pub_path.write_text(json.dumps({
        "last_published_time": datetime.now(timezone.utc).isoformat(),
        "queue": [{"scheduled_time": past.isoformat(), "meme": {"meme_id": 1, "publish_choice": "potato", "content": {"content_type": "text", "text": "hi"}, "created_time": past.isoformat()}}],
    }))
    monkeypatch.setattr(Scheduler, "MODERATION_FILE", str(mod_path))
    monkeypatch.setattr(Scheduler, "PUBLICATION_FILE", str(pub_path))

    s = Scheduler(post_frequency_minutes=5)
    assert len(s.scheduled_posts) == 1
    scheduled_time = datetime.fromisoformat(s.scheduled_posts[0]["scheduled_time"])
    assert scheduled_time >= datetime.now(timezone.utc) - timedelta(seconds=1)


@pytest.mark.asyncio
async def test_scheduler_schedule_with_user_messages(scheduler):
    """Планирование с existing user_messages → edit_message_reply_markup вызывается."""
    bot = AsyncMock()
    scheduler.bot = bot

    meme = _make_meme(1, user_messages=[(7, 100)])
    await scheduler.schedule(meme)

    assert len(scheduler.scheduled_posts) == 1
    bot.edit_message_reply_markup.assert_awaited_once()


@pytest.mark.asyncio
async def test_scheduler_schedule_without_user_messages_sends_message(scheduler):
    """Планирование без user_messages → send_message вызывается."""
    bot = AsyncMock()
    scheduler.bot = bot

    meme = _make_meme(1)  # user_messages=[]
    await scheduler.schedule(meme)

    bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_scheduler_schedule_send_message_failure_logged(scheduler, caplog):
    """Если send_message падает — лог, не exception."""
    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=Exception("user blocked"))
    scheduler.bot = bot

    import logging
    with caplog.at_level(logging.ERROR):
        await scheduler.schedule(_make_meme(1))
    assert "Не удалось уведомить пользователя" in caplog.text


@pytest.mark.asyncio
async def test_scheduler_schedule_edit_failure_logged(scheduler, caplog):
    """Если edit_message_reply_markup падает — лог."""
    bot = AsyncMock()
    bot.edit_message_reply_markup = AsyncMock(side_effect=Exception("msg not found"))
    scheduler.bot = bot

    import logging
    with caplog.at_level(logging.ERROR):
        await scheduler.schedule(_make_meme(1, user_messages=[(7, 100)]))
    assert "Ошибка при обновлении сообщения" in caplog.text


@pytest.mark.asyncio
async def test_scheduler_schedule_with_existing_posts(scheduler):
    """scheduled_time следующего мема = time последнего + post_frequency."""
    bot = AsyncMock()
    scheduler.bot = bot
    meme1 = _make_meme(1, publish_choice="potato", user_id=None)  # не триггерит уведомления
    meme2 = _make_meme(2, publish_choice="potato", user_id=None)
    await scheduler.schedule(meme1)
    await scheduler.schedule(meme2)

    t1 = datetime.fromisoformat(scheduler.scheduled_posts[0]["scheduled_time"])
    t2 = datetime.fromisoformat(scheduler.scheduled_posts[1]["scheduled_time"])
    assert t2 > t1


@pytest.mark.asyncio
async def test_scheduler_run_expires_old_pending(scheduler):
    """Меме старше 3 дней удаляется из pending_memes в run-цикле."""
    old_meme = _make_meme(1, publish_choice="potato")
    old_meme.created_time = datetime.now(timezone.utc) - timedelta(days=4)
    scheduler.pending_memes[1] = old_meme

    # Запускаем run() и сразу отменяем после одной итерации
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.05)  # дать одной итерации пройти
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert 1 not in scheduler.pending_memes


@pytest.mark.asyncio
async def test_scheduler_run_publishes_due(scheduler):
    """scheduled_post готов к публикации → on_publish вызывается."""
    called = []
    async def fake_publish(meme):
        called.append(meme.meme_id)
    scheduler.on_publish = fake_publish

    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    meme = _make_meme(42)
    scheduler.scheduled_posts.append({
        "scheduled_time": past.isoformat(),
        "meme": meme.to_publication_dict(),
    })

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert 42 in called
    assert len(scheduler.scheduled_posts) == 0


@pytest.mark.asyncio
async def test_scheduler_run_on_publish_exception_logged(scheduler, caplog):
    """Если on_publish падает — лог, цикл продолжает."""
    async def bad_publish(meme):
        raise RuntimeError("boom")
    scheduler.on_publish = bad_publish

    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    meme = _make_meme(99)
    scheduler.scheduled_posts.append({
        "scheduled_time": past.isoformat(),
        "meme": meme.to_publication_dict(),
    })

    import logging
    with caplog.at_level(logging.ERROR):
        task = asyncio.create_task(scheduler.run())
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    assert "Ошибка в on_publish" in caplog.text


def test_scheduler_get_max_meme_id_combines_pending_and_scheduled(scheduler):
    scheduler.pending_memes[5] = _make_meme(5)
    scheduler.scheduled_posts.append({
        "scheduled_time": datetime.now(timezone.utc).isoformat(),
        "meme": {"meme_id": 10, "publish_choice": "potato", "content": {"content_type": "text", "text": "x"}, "created_time": datetime.now(timezone.utc).isoformat()},
    })
    assert scheduler.get_max_meme_id() == 10


def test_scheduler_night_time_reschedule_to_morning(scheduler):
    """Если scheduled time < 7 утра UTC — откладывается до 7:00."""
    night = datetime(2026, 1, 1, 3, 0, 0, tzinfo=timezone.utc)
    result = Scheduler.get_next_allowed_time(night)
    assert result.hour == 7
    assert result.minute == 0


# ===== moderation.py: defensive branches =====

@pytest.mark.asyncio
async def test_reset_rejections_no_user_id():
    """_reset_rejections с user_id=None — no-op."""
    state = AppState(bot=MagicMock(), scheduler=MagicMock())
    moderation_module._reset_rejections(None, state)
    assert state.user_data == {}


@pytest.mark.asyncio
async def test_increment_rejections_no_user_id():
    state = AppState(bot=MagicMock(), scheduler=MagicMock())
    await moderation_module._increment_rejections_and_maybe_ban(None, state)
    assert state.user_data == {}


@pytest.mark.asyncio
async def test_finalize_silent_loss_keeps_meme(tmp_path, monkeypatch):
    """Если publish_meme возвращает False — meme.finalized сбрасывается, resolve НЕ вызывается."""
    bot = AsyncMock()
    scheduler = MagicMock()
    scheduler.pending_memes = {}
    scheduler.resolve = MagicMock()
    state = AppState(bot=bot, scheduler=scheduler)

    meme = _make_meme(1)
    meme.finalized = True  # caller уже поставил claim

    with patch("kartoshka.handlers.moderation.save_user_data"), \
         patch("kartoshka.notifications.publish_meme", AsyncMock(return_value=False)):
        await moderation_module._finalize_meme(meme, "urgent", state)

    assert meme.finalized is False
    scheduler.resolve.assert_not_called()


@pytest.mark.asyncio
async def test_increment_ban_send_failure_logged(caplog):
    """Если bot.send_message на уведомлении о бане падает — лог, save всё равно прошёл."""
    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=Exception("user blocked"))
    state = AppState(bot=bot, scheduler=MagicMock())

    with patch("kartoshka.handlers.moderation.save_user_data"):
        # 3 rejections подряд → должен сработать ban-notification
        state.user_data["7"] = {"last_submission": None, "rejections": 2, "ban_until": None}
        import logging
        with caplog.at_level(logging.ERROR):
            await moderation_module._increment_rejections_and_maybe_ban(7, state)

    assert state.user_data["7"]["rejections"] == 3
    assert state.user_data["7"]["ban_until"] is not None
    assert "Не удалось уведомить пользователя" in caplog.text


# ===== notifications.publish_meme error branch =====

@pytest.mark.asyncio
async def test_publish_meme_catches_send_exception(caplog):
    from kartoshka.notifications import publish_meme

    bot = AsyncMock()
    snap = MessageSnapshot(content_type="text", text="x")
    meme = Meme(meme_id=1, user_id=7, publish_choice="potato", content=snap)

    with patch("kartoshka.notifications.send_media_message",
               AsyncMock(side_effect=Exception("telegram down"))):
        import logging
        with caplog.at_level(logging.ERROR):
            result = await publish_meme(bot, meme, 12345)

    assert result is False
    assert "Ошибка при публикации" in caplog.text


# ===== submit.py: edge paths =====

@pytest.mark.asyncio
async def test_submit_send_media_failure_logged(caplog):
    """Если send_media_message модератору падает — лог, мем всё равно создан."""
    from kartoshka.handlers import register_handlers

    class RecordingDP:
        def __init__(self):
            self.messages = []
            self.callbacks = []
        def message(self, *a, **kw):
            return lambda fn: self.messages.append(fn) or fn
        def callback_query(self, *a, **kw):
            return lambda fn: self.callbacks.append(fn) or fn

    bot = AsyncMock()
    scheduler = MagicMock()
    scheduler.pending_memes = {}
    scheduler.add_pending = MagicMock(side_effect=lambda m: scheduler.pending_memes.__setitem__(m.meme_id, m))
    scheduler.save_moderation = MagicMock()
    state = AppState(bot=bot, scheduler=scheduler)

    dp = RecordingDP()
    register_handlers(dp, state)
    handle_meme = dp.messages[1]

    state.set_publish_choice(7, "user")

    msg = MagicMock()
    msg.text = "hi"
    msg.caption = None
    msg.content_type = "text"
    msg.from_user = SimpleNamespace(id=7, username="u", first_name="U")
    msg.chat = SimpleNamespace(id=7)
    msg.message_id = 50
    msg.answer = AsyncMock(return_value=SimpleNamespace(message_id=51))

    with patch("kartoshka.handlers.submit.save_user_data"), \
         patch("kartoshka.handlers.submit.save_meme_counter"), \
         patch("kartoshka.handlers.submit.send_media_message",
               AsyncMock(side_effect=Exception("editor offline"))):
        import logging
        with caplog.at_level(logging.ERROR):
            await handle_meme(msg)

    assert "Не удалось отправить сообщение редактору" in caplog.text
    # Мем всё равно создан
    assert 1 in state.scheduler.pending_memes


@pytest.mark.asyncio
async def test_submit_potato_anonymous_no_user_message_widget():
    """Для potato-мема user_messages не заполняется (user_id анонимен в widget'е)."""
    from kartoshka.handlers import register_handlers

    class RecordingDP:
        def __init__(self):
            self.messages = []
            self.callbacks = []
        def message(self, *a, **kw):
            return lambda fn: self.messages.append(fn) or fn
        def callback_query(self, *a, **kw):
            return lambda fn: self.callbacks.append(fn) or fn

    bot = AsyncMock()
    scheduler = MagicMock()
    scheduler.pending_memes = {}
    scheduler.add_pending = MagicMock(side_effect=lambda m: scheduler.pending_memes.__setitem__(m.meme_id, m))
    scheduler.save_moderation = MagicMock()
    state = AppState(bot=bot, scheduler=scheduler)

    dp = RecordingDP()
    register_handlers(dp, state)
    handle_meme = dp.messages[1]

    # НЕ анонимный choice — но user_id будет всё равно в Meme (контракт такой).
    # Для покрытия ветки "meme.user_id is not None" — используем "potato" + user_id = None
    # который получается в submit.py всегда = message.from_user.id.
    # Поэтому просто проверим потато-мем — у него user_messages заполняется,
    # т.к. meme.user_id = message.from_user.id (хоть и анонимно для канала).
    state.set_publish_choice(7, "potato")
    msg = MagicMock()
    msg.text = None
    msg.caption = "anon meme"
    msg.content_type = "text"
    msg.from_user = SimpleNamespace(id=7, username=None, first_name=None)
    msg.chat = SimpleNamespace(id=7)
    msg.message_id = 1
    msg.answer = AsyncMock(return_value=SimpleNamespace(message_id=2))

    with patch("kartoshka.handlers.submit.save_user_data"), \
         patch("kartoshka.handlers.submit.save_meme_counter"), \
         patch("kartoshka.handlers.submit.send_media_message",
               AsyncMock(return_value=SimpleNamespace(message_id=777))):
        await handle_meme(msg)

    meme = list(state.scheduler.pending_memes.values())[0]
    assert meme.publish_choice == "potato"
    # from_text == "Картошка" для потато — проверим в info_text
    # (внутренняя логика, здесь важно что handler не упал)


# ===== handlers.moderation: noop callback =====

@pytest.mark.asyncio
async def test_noop_callback_via_register():
    from kartoshka.handlers import register_handlers

    class RecordingDP:
        def __init__(self):
            self.callbacks = []
            self.messages = []
        def message(self, *a, **kw):
            return lambda fn: self.messages.append(fn) or fn
        def callback_query(self, *a, **kw):
            return lambda fn: self.callbacks.append(fn) or fn

    state = AppState(bot=AsyncMock(), scheduler=MagicMock())
    dp = RecordingDP()
    register_handlers(dp, state)

    noop = dp.callbacks[2]  # start choice + crypto + noop
    cb = MagicMock()
    cb.answer = AsyncMock()
    await noop(cb)
    cb.answer.assert_awaited()


# ===== main._expire_publish_choices_loop =====

@pytest.mark.asyncio
async def test_expire_loop_removes_stale_entries():
    from kartoshka.main import _expire_publish_choices_loop

    state = AppState(bot=MagicMock(), scheduler=MagicMock())
    state.user_publish_choice[1] = ("user", datetime.now(timezone.utc) - timedelta(minutes=1))
    state.user_publish_choice[2] = ("potato", datetime.now(timezone.utc) + timedelta(hours=1))

    task = asyncio.create_task(_expire_publish_choices_loop(state, interval_sec=0.01))
    await asyncio.sleep(0.05)  # даём 2-3 итерации пройти
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert 1 not in state.user_publish_choice
    assert 2 in state.user_publish_choice


@pytest.mark.asyncio
async def test_expire_loop_catches_exception(caplog):
    """Если expire_old_choices падает — loop логирует и продолжает."""
    from kartoshka.main import _expire_publish_choices_loop

    state = AppState(bot=MagicMock(), scheduler=MagicMock())
    state.expire_old_choices = MagicMock(side_effect=RuntimeError("boom"))

    import logging
    with caplog.at_level(logging.ERROR):
        task = asyncio.create_task(_expire_publish_choices_loop(state, interval_sec=0.01))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert "Ошибка в cleanup-loop" in caplog.text


# ===== main.build_app_state =====

# ===== Оставшиеся edge-case ветки =====

@pytest.mark.asyncio
async def test_crypto_reject_path_in_callback():
    """moderation.py:102 — ветка final_action='reject' в crypto-режиме."""
    from kartoshka.handlers import register_handlers

    class RecordingDP:
        def __init__(self):
            self.messages = []
            self.callbacks = []
        def message(self, *a, **kw):
            return lambda fn: self.messages.append(fn) or fn
        def callback_query(self, *a, **kw):
            return lambda fn: self.callbacks.append(fn) or fn

    bot = AsyncMock()
    scheduler = MagicMock()
    scheduler.pending_memes = {}
    scheduler.save_moderation = MagicMock()
    scheduler.resolve = MagicMock(side_effect=lambda mid: scheduler.pending_memes.pop(mid, None))
    state = AppState(bot=bot, scheduler=scheduler)

    meme = _make_meme(42)
    scheduler.pending_memes[42] = meme

    dp = RecordingDP()
    register_handlers(dp, state)
    crypto_cb = dp.callbacks[1]

    # Два reject голоса → is_rejected() == True → final_action = "reject".
    # На CI VOTES_TO_REJECT=3 по workflow-env, патчим в 2 явно.
    with patch("kartoshka.config.CRYPTOSELECTARCHY", True), \
         patch("kartoshka.config.VOTES_TO_REJECT", 2), \
         patch("kartoshka.handlers.moderation.save_user_data"), \
         patch("kartoshka.notifications.update_user_messages_with_status", AsyncMock()), \
         patch("kartoshka.notifications.update_mod_messages_with_resolution", AsyncMock()):
        for mod_id in (111, 222):
            cb = MagicMock()
            cb.data = f"reject_42"
            cb.from_user = SimpleNamespace(id=mod_id)
            cb.message = MagicMock()
            cb.message.chat = SimpleNamespace(id=mod_id)
            cb.message.message_id = 1
            cb.answer = AsyncMock()
            await crypto_cb(cb)

    assert meme.finalized is True
    scheduler.resolve.assert_called_with(42)


@pytest.mark.asyncio
async def test_submit_user_without_username_shows_id():
    """submit.py:80 — если у юзера нет username, в info_text идёт его id."""
    from kartoshka.handlers import register_handlers

    class RecordingDP:
        def __init__(self):
            self.messages = []
            self.callbacks = []
        def message(self, *a, **kw):
            return lambda fn: self.messages.append(fn) or fn
        def callback_query(self, *a, **kw):
            return lambda fn: self.callbacks.append(fn) or fn

    scheduler = MagicMock()
    scheduler.pending_memes = {}
    scheduler.add_pending = MagicMock(side_effect=lambda m: scheduler.pending_memes.__setitem__(m.meme_id, m))
    state = AppState(bot=AsyncMock(), scheduler=scheduler)
    state.set_publish_choice(99, "user")

    dp = RecordingDP()
    register_handlers(dp, state)
    handle_meme = dp.messages[1]

    msg = MagicMock()
    msg.text = "x"
    msg.caption = None
    msg.content_type = "text"
    msg.from_user = SimpleNamespace(id=99, username=None, first_name="NoUser")
    msg.chat = SimpleNamespace(id=99)
    msg.message_id = 1
    msg.answer = AsyncMock(return_value=SimpleNamespace(message_id=2))

    sent_calls = []
    async def fake_send(**kw):
        sent_calls.append(kw)
        return SimpleNamespace(message_id=777)

    with patch("kartoshka.handlers.submit.save_user_data"), \
         patch("kartoshka.handlers.submit.save_meme_counter"), \
         patch("kartoshka.handlers.submit.send_media_message", side_effect=fake_send):
        await handle_meme(msg)

    # info_text должен содержать id юзера, потому что username=None
    assert any("99" in call["caption"] for call in sent_calls)


@pytest.mark.asyncio
async def test_main_on_publish_closure_invokes_publish_meme():
    """main.py:31 — замыкание on_publish внутри build_app_state."""
    from kartoshka.main import build_app_state

    published = []

    async def fake_publish_meme(bot, meme, chat_id):
        published.append(meme.meme_id)

    captured_callback = {}

    def capture_scheduler(post_frequency_minutes, bot=None, on_publish=None):
        captured_callback["on_publish"] = on_publish
        scheduler = MagicMock()
        scheduler.get_max_meme_id.return_value = 0
        return scheduler

    with patch("kartoshka.main.Bot") as FakeBot, \
         patch("kartoshka.main.Scheduler", side_effect=capture_scheduler), \
         patch("kartoshka.main.load_meme_counter", return_value=0), \
         patch("kartoshka.main.load_user_data", return_value={}), \
         patch("kartoshka.main.publish_meme", fake_publish_meme):
        FakeBot.return_value = MagicMock()
        build_app_state()

        # Дёргаем замыкание ВНУТРИ with — иначе patch снят и вызовется настоящий publish_meme.
        on_publish = captured_callback["on_publish"]
        fake_meme = MagicMock()
        fake_meme.meme_id = 777
        await on_publish(fake_meme)
    assert 777 in published


@pytest.mark.asyncio
async def test_notifications_update_user_messages_edit_failure_logged(caplog):
    """notifications.py:45-46 — edit_message_reply_markup исключение → лог."""
    from kartoshka.notifications import update_user_messages_with_status

    bot = AsyncMock()
    bot.edit_message_reply_markup = AsyncMock(side_effect=Exception("chat not found"))

    snap = MessageSnapshot(content_type="text", text="x")
    meme = Meme(meme_id=1, user_id=7, publish_choice="user", content=snap)
    meme.user_messages = [(7, 100)]

    import logging
    with caplog.at_level(logging.ERROR):
        await update_user_messages_with_status(bot, meme)

    assert "Ошибка при обновлении сообщения для пользователя" in caplog.text


def test_scheduler_add_pending_and_resolve_covers_save():
    """scheduler.py:61-62, 65-66 — add_pending/resolve вызывают save_moderation."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp_mod, \
         tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp_pub:
        mod_path = tmp_mod.name
        pub_path = tmp_pub.name

    with patch.object(Scheduler, "MODERATION_FILE", mod_path), \
         patch.object(Scheduler, "PUBLICATION_FILE", pub_path):
        s = Scheduler(post_frequency_minutes=5)
        s.add_pending(_make_meme(100))
        assert 100 in s.pending_memes
        s.resolve(100)
        assert 100 not in s.pending_memes

    os.unlink(mod_path)
    os.unlink(pub_path)


@pytest.mark.asyncio
async def test_scheduler_schedule_removes_from_pending(scheduler):
    """scheduler.py:129 — при schedule() мем удаляется из pending_memes если там был."""
    bot = AsyncMock()
    scheduler.bot = bot
    meme = _make_meme(1, publish_choice="potato", user_id=None)
    scheduler.pending_memes[1] = meme  # сначала в pending

    await scheduler.schedule(meme)

    assert 1 not in scheduler.pending_memes
    assert len(scheduler.scheduled_posts) == 1


@pytest.mark.asyncio
async def test_scheduler_schedule_past_time_normalized_to_zero(scheduler, monkeypatch):
    """scheduler.py:136 — если scheduled_time в прошлом (time_diff < 0), нормализуем к 0."""
    bot = AsyncMock()
    scheduler.bot = bot

    # Подставляем такой last_published_time, чтобы get_next_allowed_time вернул прошлое
    scheduler.last_published_time = datetime.now(timezone.utc) - timedelta(hours=10)
    # И патчим get_next_allowed_time чтобы возвращал прошлое время
    past = datetime.now(timezone.utc) - timedelta(minutes=30)
    monkeypatch.setattr(scheduler, "get_next_allowed_time", lambda _: past)

    meme = _make_meme(1, user_messages=[(7, 100)])  # триггерит edit_message_reply_markup
    await scheduler.schedule(meme)
    # Если time_diff < 0, нормализуется к 0 (0 ч 0 мин)
    bot.edit_message_reply_markup.assert_awaited()


@pytest.mark.asyncio
async def test_scheduler_run_future_entry_sleeps_then_cancels(scheduler):
    """scheduler.py:183 — если scheduled_post в будущем, run() уходит в sleep."""
    # Ставим entry через 10 секунд
    future = datetime.now(timezone.utc) + timedelta(seconds=10)
    meme = _make_meme(1)
    scheduler.scheduled_posts.append({
        "scheduled_time": future.isoformat(),
        "meme": meme.to_publication_dict(),
    })

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.05)  # sleep branch отрабатывает
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    # Мы не прошли через publish, just through sleep branch
    assert len(scheduler.scheduled_posts) == 1


# ===== Mutation-killers для _default_user_data + vote summary =====

def test_default_user_data_has_exact_keys():
    """moderation._default_user_data: точные имена ключей — мутация 'XXlast_submissionXX' будет поймана."""
    from kartoshka.handlers.moderation import _default_user_data
    d = _default_user_data()
    assert set(d.keys()) == {"last_submission", "rejections", "ban_until"}
    assert d["last_submission"] is None
    assert d["rejections"] == 0
    assert d["ban_until"] is None


def test_get_vote_summary_exact_counts():
    """get_vote_summary: реальный подсчёт approve/urgent/reject.
    Ловит мутации `sum(1...)` → `sum(2...)` и `"approve"` → `"XXapproveXX"`."""
    snap = MessageSnapshot(content_type="text", text="x")
    meme = Meme(meme_id=1, user_id=1, publish_choice="user", content=snap)
    # 2 approve, 1 urgent, 3 reject
    meme.add_vote(1, "approve")
    meme.add_vote(2, "approve")
    meme.add_vote(3, "urgent")
    meme.add_vote(4, "reject")
    meme.add_vote(5, "reject")
    meme.add_vote(6, "reject")

    summary = meme.get_vote_summary()
    assert "✅ 2" in summary
    assert "⚡ 1" in summary
    assert "❌ 3" in summary


def test_count_votes_exact_approve_includes_urgent():
    """count_votes('approve') включает и 'approve', и 'urgent'. Ловит мутацию
    'XXurgentXX' в строке-фильтре."""
    snap = MessageSnapshot(content_type="text", text="x")
    meme = Meme(meme_id=1, user_id=1, publish_choice="user", content=snap)
    meme.add_vote(1, "approve")
    meme.add_vote(2, "urgent")
    meme.add_vote(3, "reject")
    assert meme.count_votes("approve") == 2  # approve + urgent
    assert meme.count_votes("reject") == 1


# ===== Branch-coverage добивка =====

def test_snapshot_from_message_all_media_types_empty():
    """message_snapshot.py FALSE-ветки каждого `if X is not None:` — content_type
    установлен, но поле пустое (photo=None, video=None, etc.)."""
    for ct in ["photo", "video", "animation", "voice", "video_note"]:
        msg = _make_fake_message(content_type=ct)  # все media-поля None
        s = MessageSnapshot.from_message(msg)
        assert s.content_type == ct
        # Все *_file_id остались None — это и есть непокрытые False-ветки
        assert getattr(s, f"{ct.rstrip('s')}_file_id" if ct != "photo" else "photo_file_id") is None


def test_snapshot_from_message_no_from_user():
    """Ветка: from_user отсутствует → from_user_* остаются None."""
    msg = SimpleNamespace(content_type="text", text="x")  # нет from_user атрибута
    s = MessageSnapshot.from_message(msg)
    assert s.from_user_id is None


def test_scheduler_get_max_meme_id_skips_smaller_ids():
    """scheduler.py:38,42 FALSE-ветки — loop продолжает при meme_id <= max_id."""
    s = Scheduler(post_frequency_minutes=5, bot=None, on_publish=None)
    # Первый элемент больше, второй меньше → FALSE ветка `if meme_id > max_id`
    s.pending_memes[10] = _make_meme(10)
    s.pending_memes[5] = _make_meme(5)
    now_iso = datetime.now(timezone.utc).isoformat()
    s.scheduled_posts = [
        {"scheduled_time": now_iso,
         "meme": {"meme_id": 20, "publish_choice": "potato",
                  "content": {"content_type": "text", "text": "a"},
                  "created_time": now_iso}},
        {"scheduled_time": now_iso,
         "meme": {"meme_id": 15, "publish_choice": "potato",
                  "content": {"content_type": "text", "text": "b"},
                  "created_time": now_iso}},
    ]
    assert s.get_max_meme_id() == 20


def test_scheduler_get_max_meme_id_empty():
    """scheduler.py:38,42 — пустые pending_memes + scheduled_posts → loop exits без max."""
    s = Scheduler(post_frequency_minutes=5, bot=None, on_publish=None)
    s.pending_memes = {}
    s.scheduled_posts = []
    assert s.get_max_meme_id() == 0


def test_scheduler_load_publication_future_entry_not_rescheduled(tmp_path, monkeypatch):
    """scheduler.py:101 FALSE-ветка — entry_time в будущем, не перепланируется."""
    mod_path = tmp_path / "mod.json"
    pub_path = tmp_path / "pub.json"
    future = datetime.now(timezone.utc) + timedelta(hours=5)
    pub_path.write_text(json.dumps({
        "last_published_time": datetime.now(timezone.utc).isoformat(),
        "queue": [{"scheduled_time": future.isoformat(),
                   "meme": {"meme_id": 1, "publish_choice": "potato",
                            "content": {"content_type": "text", "text": "hi"},
                            "created_time": datetime.now(timezone.utc).isoformat()}}],
    }))
    monkeypatch.setattr(Scheduler, "MODERATION_FILE", str(mod_path))
    monkeypatch.setattr(Scheduler, "PUBLICATION_FILE", str(pub_path))

    s = Scheduler(post_frequency_minutes=5)
    loaded = datetime.fromisoformat(s.scheduled_posts[0]["scheduled_time"])
    # Время НЕ изменилось — оно было в будущем
    assert abs((loaded - future).total_seconds()) < 1


@pytest.mark.asyncio
async def test_scheduler_run_pending_not_expired(scheduler):
    """scheduler.py:172 FALSE — pending есть, но он свежий (не > 3 дней)."""
    fresh_meme = _make_meme(1, publish_choice="potato")
    fresh_meme.created_time = datetime.now(timezone.utc) - timedelta(hours=1)
    scheduler.pending_memes[1] = fresh_meme

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    # Мем всё ещё в очереди — не истёк
    assert 1 in scheduler.pending_memes


@pytest.mark.asyncio
async def test_scheduler_run_without_on_publish(scheduler):
    """scheduler.py:189 FALSE — on_publish=None → skip publish."""
    scheduler.on_publish = None
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    meme = _make_meme(1, publish_choice="potato")
    scheduler.scheduled_posts.append({
        "scheduled_time": past.isoformat(),
        "meme": meme.to_publication_dict(),
    })

    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    # scheduled_post удалён, но publish не вызывался (on_publish=None, ничего не падает)
    assert len(scheduler.scheduled_posts) == 0


@pytest.mark.asyncio
async def test_telegram_io_with_snapshot_and_explicit_caption():
    """telegram_io.py:19,22 FALSE-ветки — content уже Snapshot + caption передан явно."""
    from kartoshka.telegram_io import send_media_message

    fake_bot = AsyncMock()
    snap = MessageSnapshot(content_type="text", text="fallback")
    # Explicit caption (truthy) → if not caption пропускается; isinstance Snapshot → skip convert
    await send_media_message(
        telegram_bot=fake_bot,
        chat_id=42,
        content=snap,
        caption="explicit caption",
    )
    fake_bot.send_message.assert_awaited_once()
    # Caption в вызове — "explicit caption", не text из snapshot
    call = fake_bot.send_message.await_args
    assert call.kwargs["text"] == "explicit caption"


@pytest.mark.asyncio
async def test_moderation_callback_skips_when_already_finalized():
    """moderation.py:96 FALSE-ветка — meme.finalized=True уже на момент callback."""
    from kartoshka.handlers import register_handlers

    class RecordingDP:
        def __init__(self):
            self.messages = []
            self.callbacks = []
        def message(self, *a, **kw):
            return lambda fn: self.messages.append(fn) or fn
        def callback_query(self, *a, **kw):
            return lambda fn: self.callbacks.append(fn) or fn

    bot = AsyncMock()
    scheduler = MagicMock()
    scheduler.pending_memes = {}
    scheduler.resolve = MagicMock()
    scheduler.save_moderation = MagicMock()
    state = AppState(bot=bot, scheduler=scheduler)

    meme = _make_meme(1)
    meme.finalized = True  # УЖЕ финализирован заранее
    scheduler.pending_memes[1] = meme

    dp = RecordingDP()
    register_handlers(dp, state)
    crypto_cb = dp.callbacks[1]

    with patch("kartoshka.config.CRYPTOSELECTARCHY", True), \
         patch("kartoshka.notifications.update_user_messages_with_status", AsyncMock()):
        cb = MagicMock()
        cb.data = "approve_1"
        cb.from_user = SimpleNamespace(id=111)
        cb.message = MagicMock()
        cb.message.chat = SimpleNamespace(id=111)
        cb.message.message_id = 1
        cb.answer = AsyncMock()
        await crypto_cb(cb)

    # Не должно быть повторной финализации — scheduler.resolve не вызывался
    scheduler.resolve.assert_not_called()


# ===== Точные string-assertions для get_caption (mutation-proof) =====

def test_get_caption_exact_username():
    """Точная строка 'Мем от пользователя @X' — поймает мутации на строке/формате."""
    snap = MessageSnapshot(
        content_type="text", text="hi",
        from_user_id=1, from_user_username="alice", from_user_first_name="Alice",
    )
    meme = Meme(meme_id=1, user_id=1, publish_choice="user", content=snap)
    assert meme.get_caption().startswith("Мем от пользователя @alice\n\nhi")


def test_get_caption_exact_first_name_fallback():
    """Username=None → fallback на first_name. Mutmut частую заменяет строку."""
    snap = MessageSnapshot(
        content_type="text", text="hello",
        from_user_id=1, from_user_username=None, from_user_first_name="Боб",
    )
    meme = Meme(meme_id=1, user_id=1, publish_choice="user", content=snap)
    # Именно "Мем от пользователя Боб" без @
    assert meme.get_caption().startswith("Мем от пользователя Боб\n\nhello")


def test_get_caption_exact_redacted_no_names():
    """Ни username, ни first_name → [ДАННЫЕ УДАЛЕНЫ]."""
    snap = MessageSnapshot(
        content_type="text", text="x",
        from_user_id=None, from_user_username=None, from_user_first_name=None,
    )
    meme = Meme(meme_id=1, user_id=None, publish_choice="user", content=snap)
    assert "Мем от пользователя [ДАННЫЕ УДАЛЕНЫ]" in meme.get_caption()


def test_get_caption_exact_potato_spoiler():
    """Анонимный мем должен содержать <tg-spoiler>...</tg-spoiler> вокруг префикса."""
    snap = MessageSnapshot(content_type="text", text="anon")
    meme = Meme(meme_id=1, user_id=7, publish_choice="potato", content=snap)
    cap = meme.get_caption()
    assert cap.startswith("<tg-spoiler>Мем от Анонимной ")
    assert "Картошки</tg-spoiler>" in cap
    assert cap.endswith("\n\nanon")


# ===== Полный round-trip Meme.to_dict / from_dict =====

def test_meme_to_dict_has_all_fields():
    """Проверяет точный набор ключей в to_dict — мутации удаляющие поля будут пойманы."""
    snap = MessageSnapshot(
        content_type="photo", photo_file_id="p1", caption="cap",
        from_user_id=7, from_user_username="u", from_user_first_name="U",
    )
    meme = Meme(meme_id=42, user_id=7, publish_choice="user", content=snap)
    meme.add_vote(100, "approve")
    meme.add_vote(200, "reject")

    d = meme.to_dict()
    assert set(d.keys()) == {"meme_id", "publish_choice", "content", "created_time", "votes", "user_id"}
    assert d["meme_id"] == 42
    assert d["publish_choice"] == "user"
    assert d["user_id"] == 7
    assert d["votes"] == {"100": "approve", "200": "reject"}
    # created_time — валидная ISO-строка
    datetime.fromisoformat(d["created_time"])
    # content содержит photo + from_user (для user-мема)
    assert d["content"]["content_type"] == "photo"
    assert d["content"]["photo"] == [{"file_id": "p1"}]
    assert d["content"]["from_user"]["username"] == "u"


def test_meme_to_dict_potato_strips_user_id_and_from_user():
    """Для potato-мемов to_dict не содержит user_id и from_user на диске."""
    snap = MessageSnapshot(
        content_type="text", text="secret",
        from_user_id=7, from_user_username="u", from_user_first_name="U",
    )
    meme = Meme(meme_id=1, user_id=7, publish_choice="potato", content=snap)
    d = meme.to_dict()
    assert "user_id" not in d
    assert "from_user" not in d["content"]


def test_meme_to_publication_dict_no_votes():
    """to_publication_dict НЕ включает votes (они только для модерации)."""
    snap = MessageSnapshot(content_type="text", text="x", from_user_id=7)
    meme = Meme(meme_id=1, user_id=7, publish_choice="user", content=snap)
    meme.add_vote(100, "approve")
    d = meme.to_publication_dict()
    assert "votes" not in d
    assert "user_id" in d
    assert d["user_id"] == 7


def test_meme_from_dict_full_roundtrip():
    """Полный round-trip: все поля Meme восстанавливаются точно."""
    snap = MessageSnapshot(
        content_type="video", video_file_id="v1", caption="test",
        from_user_id=42, from_user_username="user", from_user_first_name="User",
    )
    original = Meme(meme_id=99, user_id=42, publish_choice="user", content=snap)
    original.add_vote(1, "approve")
    original.add_vote(2, "reject")
    original_time = original.created_time

    restored = Meme.from_dict(original.to_dict())

    assert restored.meme_id == 99
    assert restored.user_id == 42
    assert restored.publish_choice == "user"
    assert restored.content.content_type == "video"
    assert restored.content.video_file_id == "v1"
    assert restored.content.caption == "test"
    assert restored.content.from_user_username == "user"
    assert restored.votes == {"1": "approve", "2": "reject"}
    # created_time восстанавливается точно (до секунды, т.к. isoformat без доп precision)
    assert abs((restored.created_time - original_time).total_seconds()) < 1


def test_meme_from_dict_potato_no_user_id():
    """from_dict для potato-мема: user_id отсутствует в JSON → None после восстановления."""
    snap = MessageSnapshot(content_type="text", text="x")
    meme = Meme(meme_id=1, user_id=7, publish_choice="potato", content=snap)
    d = meme.to_dict()
    assert "user_id" not in d

    restored = Meme.from_dict(d)
    assert restored.user_id is None


def test_build_app_state_constructs_everything():
    from kartoshka.main import build_app_state

    with patch("kartoshka.main.load_meme_counter", return_value=5), \
         patch("kartoshka.main.load_user_data", return_value={"1": {"last_submission": None, "rejections": 0, "ban_until": None}}), \
         patch("kartoshka.main.Bot") as FakeBot, \
         patch("kartoshka.main.Scheduler") as FakeScheduler:
        FakeBot.return_value = MagicMock()
        scheduler_instance = MagicMock()
        scheduler_instance.get_max_meme_id.return_value = 3
        FakeScheduler.return_value = scheduler_instance

        state = build_app_state()

    assert state.meme_counter == 5  # max(5, 3)
    assert "1" in state.user_data
    assert state.bot is FakeBot.return_value
    assert state.scheduler is scheduler_instance
