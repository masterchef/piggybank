import sqlite3
import logging
from functools import wraps
from flask import g, jsonify, Response
from typing import Dict, Any, Union, Tuple, Callable, Any


def normalize_account_name(name: str) -> str:
    """Normalize account names for consistency."""
    name = name.lower()
    name_mappings = {
        'victor': 'viktor'
    }
    return name_mappings.get(name, name)


def get_db() -> sqlite3.Connection:
    """Get database connection from Flask's application context."""
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

def init_db(db) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_name TEXT NOT NULL,
            auth_token TEXT NOT NULL UNIQUE
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            subscription_id INTEGER NOT NULL,
            UNIQUE (name, subscription_id),
            FOREIGN KEY (subscription_id) REFERENCES subscriptions (id)
        );
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            reason TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts (id)
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            subscription_id INTEGER NOT NULL,
            messages TEXT NOT NULL,
            last_access REAL NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (subscription_id) REFERENCES subscriptions (id)
        )
    ''')
    db.commit()
