import sqlite3
import logging
from functools import wraps
from flask import g
from piggy_bank.utils import normalize_account_name
from typing import Callable, TypedDict, Optional
from datetime import datetime

log = logging.getLogger(__name__)


class ServiceResult(TypedDict):
    """A standard result type for service functions."""

    response: dict
    error: Optional[str]


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect("pigbank.db")
        g.db.row_factory = sqlite3.Row
    return g.db


def with_db(func: Callable) -> Callable:
    """Decorator that provides database connection and commits after function execution."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        db = get_db()
        try:
            result = func(db, *args, **kwargs)
            db.commit()
            return result
        except Exception as e:
            db.rollback()
            raise e

    return wrapper


@with_db
def add_account(
    db: sqlite3.Connection, name: str, subscription_id: int
) -> ServiceResult:
    name = normalize_account_name(name)
    try:
        db.execute(
            "INSERT INTO accounts (name, subscription_id) VALUES (?, ?)",
            (name, subscription_id),
        )
        log.info(
            'Account "%s" created with balance of 0 for subscription %s',
            name,
            subscription_id,
        )
        return {
            "response": {"message": f'Account "{name}" created with balance of 0'},
            "error": None,
        }
    except sqlite3.IntegrityError:
        log.error("Attempted to create an account that already exists: %s", name)
        return {"response": {}, "error": "Account already exists"}


@with_db
def list_accounts(db: sqlite3.Connection, subscription_id: int) -> ServiceResult:
    rows = db.execute(
        """
        SELECT a.name, a.id, COALESCE(SUM(t.amount), 0) as balance
        FROM accounts a
        LEFT JOIN transactions t ON a.id = t.account_id
        WHERE a.subscription_id = ?
        GROUP BY a.id, a.name
        ORDER BY a.name
    """,
        (subscription_id,),
    ).fetchall()
    accounts = [
        {"name": row["name"], "id": row["id"], "balance": row["balance"]}
        for row in rows
    ]
    log.info("Listed %d accounts for subscription %s", len(accounts), subscription_id)
    return {"response": {"accounts": accounts}, "error": None}


@with_db
def get_balance(
    db: sqlite3.Connection, name: str, subscription_id: int
) -> ServiceResult:
    name = normalize_account_name(name)
    account = db.execute(
        "SELECT id FROM accounts WHERE name = ? AND subscription_id = ?",
        (name, subscription_id),
    ).fetchone()
    if not account:
        log.warning(
            "Attempted to get balance for non-existent account: %s in subscription %s",
            name,
            subscription_id,
        )
        return {"response": {}, "error": "Account not found"}
    account_id = account["id"]
    balance_row = db.execute(
        "SELECT COALESCE(SUM(amount), 0) as balance FROM transactions WHERE account_id = ?",
        (account_id,),
    ).fetchone()
    log.info(
        'Retrieved balance for account "%s" (id %s) in subscription %s: %s',
        name,
        account_id,
        subscription_id,
        balance_row["balance"],
    )
    return {"response": {"balance": balance_row["balance"]}, "error": None}


@with_db
def get_transactions(
    db: sqlite3.Connection, name: str, subscription_id: int, last_n: int = 5
) -> ServiceResult:
    name = normalize_account_name(name)
    account = db.execute(
        "SELECT id FROM accounts WHERE name = ? AND subscription_id = ?",
        (name, subscription_id),
    ).fetchone()
    if not account:
        log.warning(
            "Attempted to get transactions for non-existent account: %s in subscription %s",
            name,
            subscription_id,
        )
        return {"response": {}, "error": "Account not found"}
    account_id = account["id"]
    transactions = db.execute(
        """
        SELECT id, amount, reason, timestamp
        FROM transactions
        WHERE account_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """,
        (account_id, last_n),
    ).fetchall()
    transaction_list = [
        {
            "id": row["id"],
            "amount": row["amount"],
            "reason": row["reason"],
            "date": datetime.fromisoformat(row["timestamp"]).strftime("%b, %d"),
        }
        for row in transactions
    ]
    log.info(
        'Retrieved %d transactions for account "%s" in subscription %s',
        len(transaction_list),
        name,
        subscription_id,
    )
    return {
        "response": {
            "transactions": transaction_list,
            "count": len(transaction_list),
        },
        "error": None,
    }


@with_db
def add_money(
    db: sqlite3.Connection, name: str, amount: float, reason: str, subscription_id: int
) -> ServiceResult:
    name = normalize_account_name(name)
    account = db.execute(
        "SELECT id FROM accounts WHERE name = ? AND subscription_id = ?",
        (name, subscription_id),
    ).fetchone()
    if not account:
        log.warning(
            "Attempted to add money to non-existent account: %s in subscription %s",
            name,
            subscription_id,
        )
        return {"response": {}, "error": "Account not found"}
    account_id = account["id"]
    db.execute(
        "INSERT INTO transactions (account_id, amount, reason) VALUES (?, ?, ?)",
        (account_id, amount, reason),
    )
    db.commit()
    log.info(
        'Added %s to account "%s" (id %s) for reason: %s in subscription %s',
        amount,
        name,
        account_id,
        reason,
        subscription_id,
    )
    return get_balance(name, subscription_id)


@with_db
def withdraw_money(
    db: sqlite3.Connection, name: str, amount: float, reason: str, subscription_id: int
) -> ServiceResult:
    name = normalize_account_name(name)
    account = db.execute(
        "SELECT id FROM accounts WHERE name = ? AND subscription_id = ?",
        (name, subscription_id),
    ).fetchone()
    if not account:
        log.warning(
            "Attempted to withdraw money from non-existent account: %s in subscription %s",
            name,
            subscription_id,
        )
        return {"response": {}, "error": "Account not found"}
    account_id = account["id"]
    balance_row = db.execute(
        "SELECT COALESCE(SUM(amount), 0) as balance FROM transactions WHERE account_id = ?",
        (account_id,),
    ).fetchone()
    current_balance = balance_row["balance"]
    if current_balance < amount:
        log.warning(
            'Insufficient funds for withdrawal from account "%s" in subscription %s. '
            "Current balance: %s, requested amount: %s",
            name,
            subscription_id,
            current_balance,
            amount,
        )
        return {"response": {}, "error": "Insufficient funds"}
    db.execute(
        "INSERT INTO transactions (account_id, amount, reason) VALUES (?, ?, ?)",
        (account_id, -amount, reason),
    )
    db.commit()
    log.info(
        'Withdrew %s from account "%s" (id %s) ' "for reason: %s in subscription %s",
        amount,
        name,
        account_id,
        reason,
        subscription_id,
    )
    return get_balance(name, subscription_id)


@with_db
def transfer_money(
    db: sqlite3.Connection,
    from_name: str,
    to_name: str,
    amount: float,
    reason: str,
    subscription_id: int,
) -> ServiceResult:
    from_name = normalize_account_name(from_name)
    to_name = normalize_account_name(to_name)
    try:
        db.execute("BEGIN")
        from_account = db.execute(
            "SELECT id FROM accounts WHERE name = ? AND subscription_id = ?",
            (from_name, subscription_id),
        ).fetchone()
        to_account = db.execute(
            "SELECT id FROM accounts WHERE name = ? AND subscription_id = ?",
            (to_name, subscription_id),
        ).fetchone()
        if not from_account or not to_account:
            db.rollback()
            log.warning(
                "Transfer failed: one or both accounts not found in subscription %s. From: %s, To: %s",
                subscription_id,
                from_name,
                to_name,
            )
            return {
                "response": {},
                "error": "One or both accounts not found",
            }
        from_account_id = from_account["id"]
        to_account_id = to_account["id"]
        balance_row = db.execute(
            "SELECT COALESCE(SUM(amount), 0) as balance FROM transactions WHERE account_id = ?",
            (from_account_id,),
        ).fetchone()
        if balance_row["balance"] < amount:
            db.rollback()
            log.warning(
                "Transfer failed: insufficient funds in account %s in "
                "subscription %s. Balance: %s, Amount: %s",
                from_name,
                subscription_id,
                balance_row["balance"],
                amount,
            )
            return {"response": {}, "error": "Insufficient funds"}
        db.execute(
            "INSERT INTO transactions (account_id, amount, reason) VALUES (?, ?, ?)",
            (from_account_id, -amount, f"Transfer to {to_name}: {reason}"),
        )
        db.execute(
            "INSERT INTO transactions (account_id, amount, reason) VALUES (?, ?, ?)",
            (to_account_id, amount, f"Transfer from {from_name}: {reason}"),
        )
        db.commit()
        log.info(
            "Transferred %s from %s (id %s) to %s (id %s) in subscription %s",
            amount,
            from_name,
            from_account_id,
            to_name,
            to_account_id,
            subscription_id,
        )
        return {
            "response": {
                "message": f"Transferred {amount} from {from_name} to {to_name}"
            },
            "error": None,
        }
    except Exception as e:
        db.rollback()
        log.error("Transfer failed due to an unexpected error: %s", e)
        return {"response": {}, "error": "Transfer failed"}
