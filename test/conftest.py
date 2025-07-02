import os
import sqlite3
import tempfile
import pytest
from flask import Flask
from typing import Generator
from main import app as flask_app, get_db
from piggy_bank import db as db_module

# Use a test database for isolation
_db_fd, _db_path = tempfile.mkstemp()
os.close(_db_fd)


@pytest.fixture
def get_test_db() -> Generator[sqlite3.Connection, None, None]:
    """Fixture to provide a database connection for tests that don't need flask app"""
    db = db_module.init_db(_db_path)
    yield db
    db.close()


@pytest.fixture
def app() -> Generator[Flask, None, None]:
    """Create a new app instance for each test to ensure isolation."""
    flask_app.config.update(
        {
            "TESTING": True,
            "DATABASE": _db_path,
        }
    )

    with flask_app.app_context():
        db_module.create_tables(get_db())
        get_db().execute(
            "INSERT INTO subscriptions (name, auth_token) VALUES (?, ?)",
            ("test_name", "test_token"),
        )
        get_db().commit()
        yield flask_app
        get_db().close()
        os.unlink(_db_path)


# Helper to add a subscription
def add_subscription(get_test_db, family_name="test_family", auth_token="test_token"):
    db = get_test_db
    db.execute(
        "INSERT INTO subscriptions (name, auth_token) VALUES (?, ?)",
        (family_name, auth_token),
    )
    db.commit()
    cur = db.execute("SELECT id FROM subscriptions WHERE auth_token=?", (auth_token,))
    return cur.fetchone()[0]


@pytest.fixture(autouse=True)
def clear_db(app: Flask):
    """Clear all tables in the database after each test."""
    with app.app_context():
        db = get_db()
        yield
        db.execute("DELETE FROM transactions")
        db.execute("DELETE FROM accounts")
        db.execute("DELETE FROM subscriptions")
        db.commit()


@pytest.fixture
def client(app: Flask):
    """A test client for the app."""
    return app.test_client()
