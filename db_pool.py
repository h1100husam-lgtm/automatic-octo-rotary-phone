# ═══════════════════════════════════════════
# مدير اتصالات قاعدة البيانات - Connection Pool
# ═══════════════════════════════════════════
import aiosqlite
from contextlib import asynccontextmanager
from typing import AsyncIterator
from config import DB_PATH


class DatabasePool:
    """Connection pool بسيط لقاعدة البيانات SQLite."""
    _instance = None
    _connection = None

    @classmethod
    async def get_instance(cls) -> "DatabasePool":
        if cls._instance is None:
            cls._instance = DatabasePool()
            await cls._instance._init_connection()
        return cls._instance

    async def _init_connection(self):
        """تهيئة الاتصال الدائم."""
        self._connection = await aiosqlite.connect(DB_PATH)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.execute("PRAGMA journal_mode=WAL")
        await self._connection.execute("PRAGMA synchronous=NORMAL")
        await self._connection.commit()

    @classmethod
    @asynccontextmanager
    async def get_connection(cls) -> AsyncIterator[aiosqlite.Connection]:
        """الحصول على اتصال من pool."""
        if cls._instance is None:
            await cls.get_instance()
        if cls._instance._connection is None:
            await cls._instance._init_connection()
        yield cls._instance._connection

    @classmethod
    async def close(cls):
        """إغلاق الاتصال عند التوقف."""
        if cls._instance and cls._instance._connection:
            await cls._instance._connection.close()
            cls._instance._connection = None
        cls._instance = None


def get_db():
    """shortcut لـ get_connection."""
    return DatabasePool.get_connection()


async def close_db():
    """shortcut لإغلاق الاتصال."""
    await DatabasePool.close()
