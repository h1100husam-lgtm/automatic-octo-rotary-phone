# ════════════════════════════════════════════
# قاعدة بيانات مجمعة للاتصالات (PostgreSQL) أو اتصال واحد (SQLite)
# ════════════════════════════════════════════
import asyncio
import logging
from typing import AsyncIterator, Optional, Any
from contextlib import asynccontextmanager

import aiosqlite
# Optional asyncpg for PostgreSQL
try:
    import asyncpg
except ImportError:
    asyncpg = None

from config import DB_TYPE, DATABASE_URI, DB_PATH

logger = logging.getLogger("agent.db_pool")

# global pool for PostgreSQL
_db_pool: Optional[Any] = None
# global connection for SQLite (we'll keep a single connection for simplicity)
_sqlite_conn: Optional[aiosqlite.Connection] = None
# lock for sqlite connection initialization
_sqlite_lock = asyncio.Lock()


async def init_db_pool() -> None:
    """Initialize the database connection pool (PostgreSQL) or connection (SQLite)."""
    global _db_pool, _sqlite_conn
    if DB_TYPE == "postgresql":
        if asyncpg is None:
            raise RuntimeError("asyncpg is not installed. Please install it to use PostgreSQL.")
        try:
            _db_pool = await asyncpg.create_pool(
                DATABASE_URI,
                min_size=1,
                max_size=10,
                command_timeout=60,
            )
            logger.info("✅ تم إنشاء مجموعة اتصالات PostgreSQL")
        except Exception as e:
            logger.error(f"فشل إنشاء مجموعة اتصالات PostgreSQL: {e}")
            raise
    else:
        # SQLite: create a single connection (we'll reuse it)
        async with _sqlite_lock:
            if _sqlite_conn is None:
                try:
                    # DATABASE_URI is like "sqlite:///path/to/db"
                    # aiosqlite expects just the path
                    db_path = DATABASE_URI.replace("sqlite:///", "")
                    _sqlite_conn = await aiosqlite.connect(db_path)
                    # Apply performance pragmas
                    await _sqlite_conn.execute("PRAGMA journal_mode=WAL")
                    await _sqlite_conn.execute("PRAGMA synchronous=NORMAL")
                    await _sqlite_conn.execute("PRAGMA busy_timeout=5000")
                    await _sqlite_conn.execute("PRAGMA cache_size=-8000")  # 8MB cache
                    await _sqlite_conn.commit()
                    logger.info("✅ تم إنشاء اتصال SQLite")
                except Exception as e:
                    logger.error(f"فشل إنشاء اتصال SQLite: {e}")
                    raise


@asynccontextmanager
async def get_db_connection() -> AsyncIterator:
    """Get a database connection from the pool (PostgreSQL) or the single connection (SQLite)."""
    if DB_TYPE == "postgresql":
        if _db_pool is None:
            await init_db_pool()
        assert _db_pool is not None
        async with _db_pool.acquire() as connection:
            yield connection
    else:
        # SQLite
        async with _sqlite_lock:
            if _sqlite_conn is None:
                await init_db_pool()
        assert _sqlite_conn is not None
        yield _sqlite_conn


async def close_db_pool() -> None:
    """Close the database pool or connection."""
    global _db_pool, _sqlite_conn
    if DB_TYPE == "postgresql":
        if _db_pool is not None:
            await _db_pool.close()
            _db_pool = None
            logger.info("🔌 تم إغلاق مجموعة اتصالات PostgreSQL")
    else:
        if _sqlite_conn is not None:
            await _sqlite_conn.close()
            _sqlite_conn = None
            logger.info("🔌 تم إغلاق اتصال SQLite")


# Alias for backward compatibility
close_db = close_db_pool