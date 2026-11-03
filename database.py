from typing import cast

import mysql.connector
from mysql.connector.abstracts import MySQLConnectionAbstract, MySQLCursorAbstract

from config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER

## Database connection
db = cast(
    MySQLConnectionAbstract,
    mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    ),
)
db.autocommit = True


def get_db() -> MySQLConnectionAbstract:
    """Return the live DB connection, or fail loudly if it isn't connected yet."""
    assert db is not None, "Database not connected"
    return db


def get_cursor() -> MySQLCursorAbstract:
    """Ping the DB (reconnecting if needed) and return a fresh cursor."""
    conn = get_db()
    conn.ping(reconnect=True, attempts=3, delay=1)
    return conn.cursor()


def ensure_user_exists(cursor: MySQLCursorAbstract, user_id: int) -> None:
    """Create a row for this user if one doesn't exist yet. Does nothing otherwise."""
    cursor.execute(
        "INSERT IGNORE INTO user_info (user_id, xp, level, last_message) "
        "VALUES (%s, 0, 0, 0)",
        (user_id,),
    )
