import os
import sqlite3
import tempfile
import pytest
from flask import Flask, g
from typing import Generator
from main import app as flask_app
from piggy_bank.db import get_db, init_db

# Use a test database for isolation
test_db_fd, test_db_path = tempfile.mkstemp()
os.close(test_db_fd)


# Helper to add a subscription
def add_subscription(family_name="test_family", auth_token="test_token"):
    app = Flask(__name__)
    with app.app_context():
        db = sqlite3.connect(test_db_path)
        db.execute(
            "INSERT INTO subscriptions (name, auth_token) VALUES (?, ?)",
            (family_name, auth_token),
        )
        db.commit()
        cur = db.execute(
            "SELECT id FROM subscriptions WHERE auth_token=?", (auth_token,)
        )
        return cur.fetchone()[0]


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    db = sqlite3.connect(test_db_path)
    init_db(db)
    yield
    db.close()
    os.unlink(test_db_path)


@pytest.fixture
def app_context():
    app = Flask(__name__)
    with app.app_context():
        g.db = sqlite3.connect(test_db_path)
        g.db.row_factory = sqlite3.Row
        init_db(g.db)
        yield
        g.db.close()


@pytest.fixture
def app() -> Generator[Flask, None, None]:
    """Create a new app instance for each test to ensure isolation."""
    app = flask_app
    app.config.update(
        {
            "TESTING": True,
            "DATABASE": ":memory:",
        }
    )

    with app.app_context():
        db = get_db()
        init_db(db)
        yield app


@pytest.fixture
def client(app: Flask):
    """A test client for the app."""
    return app.test_client()
