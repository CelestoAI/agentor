from zerozen.memory.api import DBManager


def test_db():
    db = DBManager()
    tbl = db.open_or_create_table()
    assert db.table_names() == ["messages"]
    assert tbl is not None
