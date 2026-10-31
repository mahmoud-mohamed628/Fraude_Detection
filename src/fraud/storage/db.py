import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS predictions (
    transaction_id TEXT PRIMARY KEY,
    probability REAL NOT NULL,
    decision TEXT NOT NULL,
    latency_ms REAL NOT NULL,
    timestamp TEXT NOT NOT NULL
);
""".replace("timestamp TEXT NOT NOT NULL", "timestamp TEXT NOT NULL")


def connect(database: str = "data/fraud.db") -> sqlite3.Connection:
    path = Path(database)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(SCHEMA)
    return connection


def save_prediction(
    transaction_id: str,
    probability: float,
    decision: str,
    latency_ms: float,
    timestamp: str,
    database: str = "data/fraud.db",
) -> bool:
    """Insert once per transaction ID; return False for duplicates."""
    connection = connect(database)
    try:
        result = connection.execute(
            """INSERT OR IGNORE INTO predictions
            (transaction_id, probability, decision, latency_ms, timestamp)
            VALUES (?, ?, ?, ?, ?)""",
            (transaction_id, probability, decision, latency_ms, timestamp),
        )
        connection.commit()
        return result.rowcount == 1
    finally:
        connection.close()
