"""Тесты хранилища кандидатов в криптоселектархи."""
from kartoshka import storage


def _isolate(tmp_path, monkeypatch):
    f = str(tmp_path / "candidates.json")
    monkeypatch.setattr("kartoshka.storage.CANDIDATES_FILE", f)
    return f


def test_add_candidate_new_returns_true(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert storage.add_candidate(111, "alice", "Alice", "2026-06-02T10:00:00+00:00") is True
    cands = storage.load_candidates()
    assert len(cands) == 1
    assert cands[0]["id"] == 111
    assert cands[0]["username"] == "alice"


def test_add_candidate_idempotent(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    storage.add_candidate(111, "alice", "Alice", "2026-06-02T10:00:00+00:00")
    # повторный отклик: не дублируем, обновляем username, сохраняем первый ts
    assert storage.add_candidate(111, "alice_new", "Alice", "2026-06-02T11:00:00+00:00") is False
    storage.add_candidate(222, "bob", "Bob", "2026-06-02T10:30:00+00:00")
    cands = storage.load_candidates()
    assert {c["id"] for c in cands} == {111, 222}
    alice = next(c for c in cands if c["id"] == 111)
    assert alice["username"] == "alice_new"          # обновлён
    assert alice["ts"] == "2026-06-02T10:00:00+00:00"  # первый ts сохранён


def test_load_candidates_missing_file(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert storage.load_candidates() == []
