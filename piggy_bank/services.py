import sqlite3
import logging
from functools import wraps
from flask import g, jsonify, Response
from piggy_bank.utils import normalize_account_name
from typing import Dict, Any, Union, Tuple, Callable, Any

def get_db() -> sqlite3.Connection:
    if 'db' not in g:
        g.db = sqlite3.connect('pigbank.db')
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
def add_account(db: sqlite3.Connection, name: str, subscription_id: int) -> Union[Response, Tuple[Response, int]]:
    name = normalize_account_name(name)
    try:
        db.execute('INSERT INTO accounts (name, subscription_id) VALUES (?, ?)', (name, subscription_id))
        logging.info(f'Account "{name}" created with balance of 0 for subscription {subscription_id}')
        return jsonify({'message': f'Account "{name}" created with balance of 0'})
    except sqlite3.IntegrityError:
        logging.error(f'Attempted to create an account that already exists: {name}')
        return jsonify({'error': 'Account already exists'}), 400

@with_db
def list_accounts(db: sqlite3.Connection, subscription_id: int) -> Response:
    rows = db.execute('''
        SELECT a.name, a.id, COALESCE(SUM(t.amount), 0) as balance 
        FROM accounts a 
        LEFT JOIN transactions t ON a.id = t.account_id 
        WHERE a.subscription_id = ?
        GROUP BY a.id, a.name 
        ORDER BY a.name
    ''', (subscription_id,)).fetchall()
    accounts = [{'name': row['name'], 'id': row['id'], 'balance': row['balance']} for row in rows]
    logging.info(f'Listed {len(accounts)} accounts for subscription {subscription_id}')
    return jsonify({'accounts': accounts})

@with_db
def get_balance(db: sqlite3.Connection, name: str, subscription_id: int) -> Union[Response, Tuple[Response, int]]:
    name = normalize_account_name(name)
    account = db.execute('SELECT id FROM accounts WHERE name = ? AND subscription_id = ?', (name, subscription_id)).fetchone()
    if not account:
        logging.warning(f'Attempted to get balance for non-existent account: {name} in subscription {subscription_id}')
        return jsonify({'error': 'Account not found'}), 404
    account_id = account['id']
    balance_row = db.execute('SELECT COALESCE(SUM(amount), 0) as balance FROM transactions WHERE account_id = ?', (account_id,)).fetchone()
    logging.info(f'Retrieved balance for account "{name}" (id {account_id}) in subscription {subscription_id}: {balance_row["balance"]}')
    return jsonify({'balance': balance_row['balance']})

@with_db
def get_transactions(db: sqlite3.Connection, name: str, subscription_id: int) -> Union[Response, Tuple[Response, int]]:
    name = normalize_account_name(name)
    account = db.execute('SELECT id FROM accounts WHERE name = ? AND subscription_id = ?', (name, subscription_id)).fetchone()
    if not account:
        logging.warning(f'Attempted to get transactions for non-existent account: {name} in subscription {subscription_id}')
        return jsonify({'error': 'Account not found'}), 404
    account_id = account['id']
    transactions = db.execute('''
        SELECT id, amount, reason, strftime('%m', timestamp) as month, strftime('%d', timestamp) as day
        FROM transactions 
        WHERE account_id = ? 
        ORDER BY timestamp DESC
        LIMIT 5
    ''', (account_id,)).fetchall()
    month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    transaction_list = [
        {
            'id': row['id'],
            'amount': row['amount'],
            'reason': row['reason'],
            'date': f"{month_names[int(row['month'])]}, {int(row['day']):02d}"
        } for row in transactions
    ]
    logging.info(f'Retrieved {len(transaction_list)} transactions for account "{name}" in subscription {subscription_id}')
    return jsonify({'transactions': transaction_list, 'count': len(transaction_list)})

@with_db
def add_money(db: sqlite3.Connection, name: str, amount: float, reason: str, subscription_id: int) -> Union[Response, Tuple[Response, int]]:
    name = normalize_account_name(name)
    account = db.execute('SELECT id FROM accounts WHERE name = ? AND subscription_id = ?', (name, subscription_id)).fetchone()
    if not account:
        logging.warning(f'Attempted to add money to non-existent account: {name} in subscription {subscription_id}')
        return jsonify({'error': 'Account not found'}), 404
    account_id = account['id']
    db.execute('INSERT INTO transactions (account_id, amount, reason) VALUES (?, ?, ?)', (account_id, amount, reason))
    db.commit()
    logging.info(f'Added {amount} to account "{name}" (id {account_id}) for reason: {reason} in subscription {subscription_id}')
    return get_balance(name, subscription_id)

@with_db
def withdraw_money(db: sqlite3.Connection, name: str, amount: float, reason: str, subscription_id: int) -> Union[Response, Tuple[Response, int]]:
    name = normalize_account_name(name)
    account = db.execute('SELECT id FROM accounts WHERE name = ? AND subscription_id = ?', (name, subscription_id)).fetchone()
    if not account:
        logging.warning(f'Attempted to withdraw money from non-existent account: {name} in subscription {subscription_id}')
        return jsonify({'error': 'Account not found'}), 404
    account_id = account['id']
    balance_row = db.execute('SELECT COALESCE(SUM(amount), 0) as balance FROM transactions WHERE account_id = ?', (account_id,)).fetchone()
    current_balance = balance_row['balance']
    if current_balance < amount:
        logging.warning(f'Insufficient funds for withdrawal from account "{name}" in subscription {subscription_id}. Current balance: {current_balance}, requested amount: {amount}')
        return jsonify({'error': 'Insufficient funds'}), 400
    db.execute('INSERT INTO transactions (account_id, amount, reason) VALUES (?, ?, ?)', (account_id, -amount, reason))
    db.commit()
    logging.info(f'Withdrew {amount} from account "{name}" (id {account_id}) for reason: {reason} in subscription {subscription_id}')
    return get_balance(name, subscription_id)

@with_db
def transfer_money(db: sqlite3.Connection, from_name: str, to_name: str, amount: float, reason: str, subscription_id: int) -> Union[Response, Tuple[Response, int]]:
    from_name = normalize_account_name(from_name)
    to_name = normalize_account_name(to_name)
    try:
        db.execute('BEGIN')
        from_account = db.execute('SELECT id FROM accounts WHERE name = ? AND subscription_id = ?', (from_name, subscription_id)).fetchone()
        to_account = db.execute('SELECT id FROM accounts WHERE name = ? AND subscription_id = ?', (to_name, subscription_id)).fetchone()
        if not from_account or not to_account:
            db.rollback()
            logging.warning(f'Transfer failed: one or both accounts not found in subscription {subscription_id}. From: {from_name}, To: {to_name}')
            return jsonify({'error': 'One or both accounts not found'}), 404
        from_account_id = from_account['id']
        to_account_id = to_account['id']
        balance_row = db.execute('SELECT COALESCE(SUM(amount), 0) as balance FROM transactions WHERE account_id = ?', (from_account_id,)).fetchone()
        if balance_row['balance'] < amount:
            db.rollback()
            logging.warning(f'Transfer failed: insufficient funds in account {from_name} in subscription {subscription_id}. Balance: {balance_row["balance"]}, Amount: {amount}')
            return jsonify({'error': 'Insufficient funds'}), 400
        db.execute('INSERT INTO transactions (account_id, amount, reason) VALUES (?, ?, ?)', (from_account_id, -amount, f'Transfer to {to_name}: {reason}'))
        db.execute('INSERT INTO transactions (account_id, amount, reason) VALUES (?, ?, ?)', (to_account_id, amount, f'Transfer from {from_name}: {reason}'))
        db.commit()
        logging.info(f'Transferred {amount} from {from_name} (id {from_account_id}) to {to_name} (id {to_account_id}) in subscription {subscription_id}')
        return jsonify({'message': f'Transferred {amount} from {from_name} to {to_name}'})
    except Exception as e:
        db.rollback()
        logging.error(f'Transfer failed due to an unexpected error: {e}')
        return jsonify({'error': 'Transfer failed'}), 500
