import os
import tempfile
import sqlite3
import pytest
from flask import Flask, g
from piggy_bank import services
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from main import init_db

# Use a test database for isolation
test_db_fd, test_db_path = tempfile.mkstemp()

class DummyResponse:
    def __init__(self, data, status_code=200):
        self.data = data
        self.status_code = status_code

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    db = sqlite3.connect(test_db_path)
    init_db(db)
    yield
    db.close()
    os.close(test_db_fd)
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

# Helper to add a subscription
def add_subscription(family_name="test_family", auth_token="test_token"):
    app = Flask(__name__)
    with app.app_context():
        db = sqlite3.connect(test_db_path)
        db.execute('INSERT INTO subscriptions (family_name, auth_token) VALUES (?, ?)', (family_name, auth_token))
        db.commit()
        cur = db.execute('SELECT id FROM subscriptions WHERE auth_token=?', (auth_token,))
        return cur.fetchone()[0]

def get_status_code(resp):
    if isinstance(resp, tuple):
        return resp[1]
    return getattr(resp, 'status_code', None)

def test_add_and_list_account(app_context):
    sub_id = add_subscription()
    resp = services.add_account("Alice", sub_id)
    assert get_status_code(resp) == 200 or get_status_code(resp) == 201
    resp = services.list_accounts(sub_id)
    assert get_status_code(resp) == 200
    assert b"alice" in resp.data

def test_get_balance_and_transactions(app_context):
    sub_id = add_subscription("fam2", "token2")
    services.add_account("Bob", sub_id)
    resp = services.get_balance("Bob", sub_id)
    assert get_status_code(resp) == 200 or get_status_code(resp) == 201
    resp = services.get_transactions("Bob", sub_id)
    assert get_status_code(resp) == 200 or get_status_code(resp) == 201

def test_add_and_withdraw_money(app_context):
    sub_id = add_subscription("fam3", "token3")
    services.add_account("Charlie", sub_id)
    resp = services.add_money("Charlie", 50.0, "deposit", sub_id)
    assert get_status_code(resp) == 200 or get_status_code(resp) == 201
    resp = services.withdraw_money("Charlie", 20.0, "withdraw", sub_id)
    assert get_status_code(resp) == 200 or get_status_code(resp) == 201

def test_transfer_money(app_context):
    sub_id = add_subscription("fam4", "token4")
    services.add_account("Daisy", sub_id)
    services.add_account("Eve", sub_id)
    services.add_money("Daisy", 100.0, "deposit", sub_id)
    resp = services.transfer_money("Daisy", "Eve", 30.0, "gift", sub_id)
    assert get_status_code(resp) == 200 or get_status_code(resp) == 201
