import aiomysql


from config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER

pool: aiomysql.Pool | None = None


async def init_pool() -> None:
    """Create the connection pool. Call once at startup, before loading cogs."""
    global pool
    pool = await aiomysql.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        autocommit=True,
        minsize=1,
        maxsize=5,
        pool_recycle=280, 
    )


async def close_pool() -> None:
    if pool is not None:
        pool.close()
        await pool.wait_closed()


def get_pool() -> aiomysql.Pool:
    assert pool is not None, "Database pool not initialised"
    return pool


async def ensure_user_exists(cursor: aiomysql.Cursor, user_id: int) -> None:
    await cursor.execute(
        "INSERT IGNORE INTO user_info (user_id, xp, level, last_message) "
        "VALUES (%s, 0, 0, 0)",
        (user_id,),
    )