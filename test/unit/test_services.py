import os
from piggy_bank import services
import sys

from conftest import add_subscription, add_account

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


def test_add_and_list_account(get_test_db):
    services.add_account(get_test_db, "test_account", 1)
    result = services.list_accounts(get_test_db, 1)
    assert result["error"] is None
    assert "accounts" in result["response"]
    assert any(acc["name"] == "test_account" for acc in result["response"]["accounts"])


def test_get_balance_and_transactions(get_test_db):
    sub_id = add_subscription(get_test_db, "fam2", "token2")
    account_id = add_account(get_test_db, "viktor", sub_id)
    services.add_money(get_test_db, account_id, 100, "initial deposit", sub_id)
    result = services.get_balance(get_test_db, account_id, sub_id)
    assert result["error"] is None
    assert "balance" in result["response"]

    result = services.get_transactions(get_test_db, account_id, sub_id)
    assert result["error"] is None
    assert "transactions" in result["response"]
    assert result["response"]["transactions"][0]["amount"] == 100


def test_add_and_withdraw_money(get_test_db):
    sub_id = add_subscription(get_test_db, "fam3", "token3")
    account_id = add_account(get_test_db, "viktor", sub_id)
    services.add_money(get_test_db, account_id, 100, "initial deposit", sub_id)
    result = services.add_money(get_test_db, account_id, 50, "deposit", sub_id)
    assert result["error"] is None
    assert result["response"]["balance"] == 150

    result = services.withdraw_money(get_test_db, account_id, 100, "withdraw", sub_id)
    assert result["error"] is None
    assert result["response"]["balance"] == 50


def test_transfer_money(get_test_db):
    sub_id = add_subscription(get_test_db, "fam4", "token4")
    viktor_account_id = add_account(get_test_db, "viktor", sub_id)
    alice_account_id = add_account(get_test_db, "alice", sub_id)
    services.add_money(get_test_db, viktor_account_id, 100, "initial deposit", sub_id)
    result = services.transfer_money(get_test_db, viktor_account_id, alice_account_id, 50, "gift", sub_id)
    assert result["error"] is None
    assert "message" in result["response"]

    viktor_balance = services.get_balance(get_test_db, viktor_account_id, sub_id)
    alice_balance = services.get_balance(get_test_db, alice_account_id, sub_id)

    assert viktor_balance["response"]["balance"] == 50
    assert alice_balance["response"]["balance"] == 50
