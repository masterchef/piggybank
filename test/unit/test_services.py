import os
from piggy_bank import services
import sys

from conftest import add_subscription

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


def test_add_and_list_account(app_context):
    sub_id = add_subscription()
    result = services.add_account("Alice", sub_id)
    assert result["error"] is None
    assert "message" in result["response"]

    result = services.list_accounts(sub_id)
    assert result["error"] is None
    assert "accounts" in result["response"]
    assert any(acc["name"] == "alice" for acc in result["response"]["accounts"])


def test_get_balance_and_transactions(app_context):
    sub_id = add_subscription("fam2", "token2")
    services.add_account("Bob", sub_id)
    result = services.get_balance("Bob", sub_id)
    assert result["error"] is None
    assert "balance" in result["response"]

    result = services.get_transactions("Bob", sub_id)
    assert result["error"] is None
    assert "transactions" in result["response"]


def test_add_and_withdraw_money(app_context):
    sub_id = add_subscription("fam3", "token3")
    services.add_account("Charlie", sub_id)
    result = services.add_money("Charlie", 50.0, "deposit", sub_id)
    assert result["error"] is None
    assert result["response"]["balance"] == 50.0

    result = services.withdraw_money("Charlie", 20.0, "withdraw", sub_id)
    assert result["error"] is None
    assert result["response"]["balance"] == 30.0


def test_transfer_money(app_context):
    sub_id = add_subscription("fam4", "token4")
    services.add_account("Daisy", sub_id)
    services.add_account("Eve", sub_id)
    services.add_money("Daisy", 100.0, "deposit", sub_id)
    result = services.transfer_money("Daisy", "Eve", 30.0, "gift", sub_id)
    assert result["error"] is None
    assert "message" in result["response"]

    daisy_balance = services.get_balance("Daisy", sub_id)
    eve_balance = services.get_balance("Eve", sub_id)

    assert daisy_balance["response"]["balance"] == 70.0
    assert eve_balance["response"]["balance"] == 30.0
