import logging
import os
import sqlite3
import sys
import time
from datetime import datetime

import pytest

from piggy_bank import db as db_module
from piggy_bank import services

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


def test_remove_account_after_cents_cancel_out(get_test_db):
    # 0.10 + 0.20 - 0.30 is 2.8e-17 in floating point, which used to block removal.
    sub_id = add_subscription(get_test_db, "fam_cents", "token_cents")
    account_id = add_account(get_test_db, "ana", sub_id)
    services.add_money(get_test_db, account_id, 0.10, "cat", sub_id)
    services.add_money(get_test_db, account_id, 0.20, "tidy", sub_id)
    result = services.withdraw_money(get_test_db, account_id, 0.30, "sticker", sub_id)
    assert result == {"response": {"balance": 0}, "error": None}

    result = services.remove_account(get_test_db, account_id, sub_id)
    assert result["error"] is None
    assert services.get_accounts(get_test_db, sub_id)["response"]["accounts"] == []


def test_remove_account_with_existing_float_dust(get_test_db):
    # Rows written before amounts were rounded must not block removal either.
    sub_id = add_subscription(get_test_db, "fam_dust", "token_dust")
    account_id = add_account(get_test_db, "tom", sub_id)
    get_test_db.executemany(
        "INSERT INTO transactions (account_id, amount, reason) VALUES (?, ?, ?)",
        [(account_id, 0.1, "a"), (account_id, 0.2, "b"), (account_id, -0.30000000000000004, "c")],
    )
    get_test_db.commit()
    assert services.get_accounts(get_test_db, sub_id)["response"]["accounts"][0]["balance"] == 0
    assert services.remove_account(get_test_db, account_id, sub_id)["error"] is None


def test_withdraw_exact_balance_with_float_sums(get_test_db):
    sub_id = add_subscription(get_test_db, "fam_exact", "token_exact")
    account_id = add_account(get_test_db, "mia", sub_id)
    services.add_money(get_test_db, account_id, 0.10, "a", sub_id)
    services.add_money(get_test_db, account_id, 0.20, "b", sub_id)
    # 0.1 + 0.2 sums to 0.30000000000000004; withdrawing 0.3 must still work, and so must 0.31 fail.
    assert services.withdraw_money(get_test_db, account_id, 0.31, "too much", sub_id)["error"] == "Insufficient funds"
    assert services.withdraw_money(get_test_db, account_id, 0.30, "all", sub_id)["error"] is None


def test_amounts_must_be_positive_cents(get_test_db):
    sub_id = add_subscription(get_test_db, "fam_amt", "token_amt")
    a = add_account(get_test_db, "a", sub_id)
    b = add_account(get_test_db, "b", sub_id)
    error = "Amount must be at least $0.01"
    assert services.add_money(get_test_db, a, 0.001, "dust", sub_id)["error"] == error
    assert services.add_money(get_test_db, a, -5, "negative", sub_id)["error"] == error
    assert services.withdraw_money(get_test_db, a, -5, "negative", sub_id)["error"] == error
    assert services.transfer_money(get_test_db, a, b, 0, "zero", sub_id)["error"] == error
    assert services.add_money(get_test_db, a, 1.239, "rounded", sub_id)["response"] == {"balance": 1.24}


def test_account_names_are_case_insensitive(get_test_db):
    sub_id = add_subscription(get_test_db, "fam_case", "token_case")
    assert services.add_account(get_test_db, "Switch", sub_id)["error"] is None

    result = services.add_account(get_test_db, "  switch ", sub_id)
    assert result["error"] == 'An account named "Switch" already exists'
    assert services.add_account(get_test_db, "   ", sub_id)["error"] == "Account name is required"

    # The same name is still fine in another family's subscription.
    other_sub = add_subscription(get_test_db, "fam_case2", "token_case2")
    assert services.add_account(get_test_db, "switch", other_sub)["error"] is None


def test_existing_database_gets_case_insensitive_names(tmp_path):
    # A database created before the case-insensitive index existed.
    path = str(tmp_path / "old.db")
    old = sqlite3.connect(path)
    old.executescript("""
        CREATE TABLE subscriptions (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            auth_token TEXT NOT NULL UNIQUE);
        CREATE TABLE accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            subscription_id INTEGER NOT NULL, UNIQUE (name, subscription_id));
        INSERT INTO subscriptions (name, auth_token) VALUES ('fam', 't');
        INSERT INTO accounts (name, subscription_id) VALUES ('Vinny', 1);
        """)
    old.close()

    db = db_module.init_db(path)
    assert services.add_account(db, "VINNY", 1)["error"] == 'An account named "Vinny" already exists'
    db.close()


def test_existing_case_duplicates_do_not_block_startup(tmp_path, caplog):
    path = str(tmp_path / "dupes.db")
    db = db_module.init_db(path)
    db.execute("DROP INDEX idx_accounts_subscription_name_nocase")
    db.execute("INSERT INTO subscriptions (name, auth_token) VALUES ('fam', 't')")
    db.executemany("INSERT INTO accounts (name, subscription_id) VALUES (?, 1)", [("Switch",), ("switch",)])
    db.commit()
    db.close()

    with caplog.at_level(logging.WARNING):
        db = db_module.init_db(path)
    assert "Switch, switch" in caplog.text
    db.close()


def test_accounts_listed_alphabetically_ignoring_case(get_test_db):
    sub_id = add_subscription(get_test_db, "fam_sort", "token_sort")
    for name in ["video games", "Vivian", "Vaiva"]:
        services.add_account(get_test_db, name, sub_id)
    names = [a["name"] for a in services.get_accounts(get_test_db, sub_id)["response"]["accounts"]]
    assert names == ["Vaiva", "video games", "Vivian"]


def test_transactions_in_same_second_are_newest_first(get_test_db):
    sub_id = add_subscription(get_test_db, "fam_order", "token_order")
    account_id = add_account(get_test_db, "tom", sub_id)
    get_test_db.executemany(
        "INSERT INTO transactions (account_id, amount, reason, timestamp) VALUES (?, ?, ?, '2026-11-11 20:00:00')",
        [(account_id, 1, "first"), (account_id, 2, "second"), (account_id, 3, "third")],
    )
    get_test_db.commit()
    result = services.get_transactions(get_test_db, account_id, sub_id)
    assert [t["reason"] for t in result["response"]["transactions"]] == ["third", "second", "first"]


@pytest.fixture
def pacific_time(monkeypatch):
    monkeypatch.setenv("TZ", "America/Los_Angeles")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def test_transaction_date_uses_local_time_and_year(pacific_time):
    now = datetime(2026, 11, 12, 9, 0).astimezone()
    # 03:00 UTC on Nov 12 is still the evening of Nov 11 in California.
    assert services.format_transaction_date("2026-11-12 03:00:00", now) == "Nov 11"
    assert services.format_transaction_date("2026-11-12 20:00:00", now) == "Nov 12"
    assert services.format_transaction_date("2025-03-05 20:00:00", now) == "Mar 5, 2025"
