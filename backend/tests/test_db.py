from app.db import Database


def test_database_persists_messages(tmp_path):
    db = Database(tmp_path / "agent.sqlite3")
    db.initialize()
    db.upsert_conversation("web:default", "web")
    assert db.add_message("web:default", "user", "你好")
    assert db.add_message("web:default", "assistant", "你好，我在")
    rows = db.list_messages("web:default")
    assert [row["role"] for row in rows] == ["user", "assistant"]


def test_duplicate_external_message_is_ignored(tmp_path):
    db = Database(tmp_path / "agent.sqlite3")
    db.initialize()
    db.upsert_conversation("wx:u1", "wechat", "u1")
    assert db.add_message("wx:u1", "user", "hello", "m1")
    assert not db.add_message("wx:u1", "user", "hello again", "m1")
