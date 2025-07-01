import sqlite3
import pytest
from flask import Flask
from piggy_bank.db import get_db, init_db, normalize_account_name, with_db


# Use an in-memory database for testing
@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["DATABASE"] = ":memory:"

    with app.app_context():
        db = get_db()
        init_db(db)
        yield app


def test_normalize_account_name():
    assert normalize_account_name("victor") == "viktor"
    assert normalize_account_name("John") == "john"
    assert normalize_account_name("Jane") == "jane"


def test_get_db(app: Flask):
    with app.app_context():
        db = get_db()
        assert db is not None
        assert isinstance(db, sqlite3.Connection)
        # Test that get_db returns the same connection within the same context
        db2 = get_db()
        assert db is db2


def test_init_db(app: Flask):
    with app.app_context():
        db = get_db()
        # init_db is called in the fixture, so we just check the tables
        cursor = db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        assert "subscriptions" in tables
        assert "accounts" in tables
        assert "transactions" in tables
        assert "sessions" in tables


def test_with_db_decorator(app: Flask):
    @with_db
    def sample_db_operation(db: sqlite3.Connection, value: str):
        db.execute("CREATE TABLE IF NOT EXISTS test_table (id INTEGER, value TEXT)")
        db.execute("INSERT INTO test_table (id, value) VALUES (?, ?)", (1, value))
        cursor = db.cursor()
        cursor.execute("SELECT value FROM test_table WHERE id = 1")
        return cursor.fetchone()[0]

    with app.app_context():
        result = sample_db_operation("test_value")
        assert result == "test_value"

        # Check if commit was successful
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT value FROM test_table WHERE id = 1")
        assert cursor.fetchone()[0] == "test_value"


def test_with_db_decorator_rollback(app: Flask):
    @with_db
    def failing_op(db: sqlite3.Connection):
        # Assuming test_table exists from previous test or is created here
        db.execute("CREATE TABLE IF NOT EXISTS test_table (id INTEGER, value TEXT)")
        db.execute(
            "INSERT INTO test_table (id, value) VALUES (?, ?)", (2, "fail_value")
        )
        raise ValueError("test error")

    with app.app_context():
        with pytest.raises(ValueError):
            failing_op()

        # Check if rollback was successful
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM test_table WHERE id = 2")
        assert cursor.fetchone() is None
