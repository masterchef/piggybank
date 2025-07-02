import os
from piggy_bank import services
import sys

from conftest import add_subscription

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


def test_add_and_list_account(get_test_db):
    services.add_account(get_test_db, "test_account", 1)
    result = services.list_accounts(get_test_db, 1)
    assert result["error"] is None
    assert "accounts" in result["response"]
    assert any(acc["name"] == "test_account" for acc in result["response"]["accounts"])


def test_get_balance_and_transactions(get_test_db):
    sub_id = add_subscription(get_test_db, "fam2", "token2")
    services.add_account(get_test_db, "viktor", sub_id)
    services.add_money(get_test_db, "viktor", 100, "initial deposit", sub_id)
    result = services.get_balance(get_test_db, "viktor", sub_id)
    assert result["error"] is None
    assert "balance" in result["response"]

    result = services.get_transactions(get_test_db, "viktor", sub_id)
    assert result["error"] is None
    assert "transactions" in result["response"]
    assert result["response"]["transactions"][0]["amount"] == 100


def test_add_and_withdraw_money(get_test_db):
    sub_id = add_subscription(get_test_db, "fam3", "token3")
    services.add_account(get_test_db, "viktor", sub_id)
    services.add_money(get_test_db, "viktor", 100, "initial deposit", sub_id)
    result = services.add_money(get_test_db, "viktor", 50, "deposit", sub_id)
    assert result["error"] is None
    assert result["response"]["balance"] == 150

    result = services.withdraw_money(get_test_db, "viktor", 100, "withdraw", sub_id)
    assert result["error"] is None
    assert result["response"]["balance"] == 50


def test_transfer_money(get_test_db):
    sub_id = add_subscription(get_test_db, "fam4", "token4")
    services.add_account(get_test_db, "viktor", sub_id)
    services.add_account(get_test_db, "alice", sub_id)
    services.add_money(get_test_db, "viktor", 100, "initial deposit", sub_id)
    result = services.transfer_money(get_test_db, "viktor", "alice", 50, "gift", sub_id)
    assert result["error"] is None
    assert "message" in result["response"]

    daisy_balance = services.get_balance(get_test_db, "viktor", sub_id)
    eve_balance = services.get_balance(get_test_db, "alice", sub_id)

    assert daisy_balance["response"]["balance"] == 50
    assert eve_balance["response"]["balance"] == 50
