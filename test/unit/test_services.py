import os
from piggy_bank import services
import sys

from conftest import add_subscription, add_account

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


def test_add_and_list_account(get_test_db):
    services.add_account(get_test_db, "test_account", 1)
    result = services.get_accounts(get_test_db, 1)
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


def test_remove_account_success_empty_account(get_test_db):
    """Test successful removal of account with no transactions."""
    sub_id = add_subscription(get_test_db, "fam5", "token5")
    account_id = add_account(get_test_db, "test_user", sub_id)

    result = services.remove_account(get_test_db, account_id, sub_id)
    assert result["error"] is None
    assert "message" in result["response"]
    assert "test_user" in result["response"]["message"]
    assert "0 associated transactions removed" in result["response"]["message"]

    # Verify account is actually removed
    accounts_result = services.get_accounts(get_test_db, sub_id)
    assert result["error"] is None
    account_names = [acc["name"] for acc in accounts_result["response"]["accounts"]]
    assert "test_user" not in account_names


def test_remove_account_success_zero_balance(get_test_db):
    """Test successful removal of account with transactions that sum to zero."""
    sub_id = add_subscription(get_test_db, "fam6", "token6")
    account_id = add_account(get_test_db, "test_user", sub_id)

    # Add and then withdraw money to create transactions but zero balance
    services.add_money(get_test_db, account_id, 100, "deposit", sub_id)
    services.withdraw_money(get_test_db, account_id, 100, "withdrawal", sub_id)

    # Verify balance is zero
    balance_result = services.get_balance(get_test_db, account_id, sub_id)
    assert balance_result["response"]["balance"] == 0

    result = services.remove_account(get_test_db, account_id, sub_id)
    assert result["error"] is None
    assert "message" in result["response"]
    assert "test_user" in result["response"]["message"]
    assert "2 associated transactions removed" in result["response"]["message"]

    # Verify account and transactions are removed
    accounts_result = services.get_accounts(get_test_db, sub_id)
    account_names = [acc["name"] for acc in accounts_result["response"]["accounts"]]
    assert "test_user" not in account_names

    # Verify transactions are removed
    transactions_result = services.get_transactions(get_test_db, account_id, sub_id)
    assert transactions_result["error"] == "Account not found"


def test_remove_account_fail_positive_balance(get_test_db):
    """Test failure when account has positive balance."""
    sub_id = add_subscription(get_test_db, "fam7", "token7")
    account_id = add_account(get_test_db, "test_user", sub_id)
    services.add_money(get_test_db, account_id, 50, "deposit", sub_id)

    result = services.remove_account(get_test_db, account_id, sub_id)
    assert result["error"] is not None
    assert "balance of 50" in result["error"]
    assert "withdraw remaining balance first" in result["error"]

    # Verify account still exists
    accounts_result = services.get_accounts(get_test_db, sub_id)
    account_names = [acc["name"] for acc in accounts_result["response"]["accounts"]]
    assert "test_user" in account_names


def test_remove_account_fail_negative_balance(get_test_db):
    """Test failure when account has negative balance."""
    sub_id = add_subscription(get_test_db, "fam8", "token8")
    account_id = add_account(get_test_db, "test_user", sub_id)
    # Create negative balance by adding debt transaction directly
    get_test_db.execute(
        "INSERT INTO transactions (account_id, amount, reason) VALUES (?, ?, ?)",
        (account_id, -25, "debt"),
    )
    get_test_db.commit()

    result = services.remove_account(get_test_db, account_id, sub_id)
    assert result["error"] is not None
    assert "balance of -25" in result["error"]
    assert "withdraw remaining balance first" in result["error"]

    # Verify account still exists
    accounts_result = services.get_accounts(get_test_db, sub_id)
    account_names = [acc["name"] for acc in accounts_result["response"]["accounts"]]
    assert "test_user" in account_names


def test_remove_account_fail_nonexistent_account(get_test_db):
    """Test failure when account doesn't exist."""
    sub_id = add_subscription(get_test_db, "fam9", "token9")

    result = services.remove_account(get_test_db, 99999, sub_id)
    assert result["error"] == "Account not found"


def test_remove_account_fail_wrong_subscription(get_test_db):
    """Test failure when account doesn't belong to subscription."""
    sub_id1 = add_subscription(get_test_db, "fam10", "token10")
    sub_id2 = add_subscription(get_test_db, "fam11", "token11")
    account_id = add_account(get_test_db, "test_user", sub_id1)

    # Try to remove account using wrong subscription
    result = services.remove_account(get_test_db, account_id, sub_id2)
    assert result["error"] == "Account not found"

    # Verify account still exists in correct subscription
    accounts_result = services.get_accounts(get_test_db, sub_id1)
    account_names = [acc["name"] for acc in accounts_result["response"]["accounts"]]
    assert "test_user" in account_names
