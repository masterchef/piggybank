import sqlite3


def normalize_account_name(name: str) -> str:
    """Normalize account names for consistency."""
    name = name.lower()
    name_mappings = {"victor": "viktor"}
    return name_mappings.get(name, name)


def init_db(path: str) -> sqlite3.Connection:
    db = sqlite3.connect(path, check_same_thread=False)
    db.row_factory = sqlite3.Row
    create_tables(db)
    return db


def create_tables(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            auth_token TEXT NOT NULL UNIQUE
        )
    """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            subscription_id INTEGER NOT NULL,
            UNIQUE (name, subscription_id),
            FOREIGN KEY (subscription_id) REFERENCES subscriptions (id)
        );
    """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            reason TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts (id)
        )
    """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            subscription_id INTEGER NOT NULL,
            messages TEXT NOT NULL,
            last_access REAL NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (subscription_id) REFERENCES subscriptions (id)
        )
    """
    )
    db.commit()
