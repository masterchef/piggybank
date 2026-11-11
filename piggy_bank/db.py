import logging
import sqlite3

log = logging.getLogger(__name__)


def normalize_account_name(name: str) -> str:
    """Normalize account names for consistency."""
    name = name.lower()
    name_mappings = {"victor": "viktor"}
    return name_mappings.get(name, name)


def init_db(path: str) -> sqlite3.Connection:
    db = sqlite3.connect(path, check_same_thread=False)
    db.row_factory = sqlite3.Row
    # WAL avoids a full journal rewrite on every commit, which is slow on a Raspberry Pi SD card.
    # synchronous=NORMAL is safe with WAL: a crash can't corrupt the DB, only lose the last commit on power loss.
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
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
    # Balance sums and "last N transactions" filter by account and sort by time.
    db.execute("CREATE INDEX IF NOT EXISTS idx_transactions_account_time ON transactions (account_id, timestamp)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_accounts_subscription ON accounts (subscription_id)")
    # Finding a subscription's latest session, and deleting expired ones.
    db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_subscription_access ON sessions (subscription_id, last_access)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_access ON sessions (last_access)")
    db.commit()
    _ensure_case_insensitive_account_names(db)


def _ensure_case_insensitive_account_names(db: sqlite3.Connection) -> None:
    """Make account names unique per subscription regardless of case ("Switch" == "switch").

    Siri transcriptions vary in capitalization, which used to create duplicate accounts.
    An index works for existing databases too, without rebuilding the accounts table.
    """
    try:
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_subscription_name_nocase "
            "ON accounts (subscription_id, name COLLATE NOCASE)"
        )
        db.commit()
    except sqlite3.IntegrityError:
        # Existing case-only duplicates block the index; keep running and say which ones to merge.
        duplicates = db.execute(
            "SELECT subscription_id, GROUP_CONCAT(name, ', ') AS names FROM accounts "
            "GROUP BY subscription_id, name COLLATE NOCASE HAVING COUNT(*) > 1"
        ).fetchall()
        log.warning(
            "Account names are not case-insensitive yet: remove or rename these duplicates: %s",
            "; ".join(f"subscription {row[0]}: {row[1]}" for row in duplicates),
        )
