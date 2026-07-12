# ═══════════════════════════════════════════
# نظام الذاكرة وقاعدة البيانات
# يدعم كلاً من SQLite (للتطوير) وPostgreSQL (للتشغيل على Render عبر Supabase)
# ════════════════════════════════════════════
import asyncio
import logging
from datetime import datetime
from typing import Any, List, Tuple, Optional, Dict

from db_pool import get_db_connection, init_db_pool, close_db_pool
from config import DB_TYPE

logger = logging.getLogger("agent.memory")


def _adapt_query(query: str) -> str:
    """Convert ? placeholders to $1, $2, ... for PostgreSQL.
    Assumes no ? inside string literals (safe for our queries).
    """
    if DB_TYPE == "postgresql":
        parts = question_mark_split(query)
        if len(parts) == 1:
            return query
        out = []
        for i, part in enumerate(parts[:-1]):
            out.append(part)
            out.append(f'${i+1}')
        out.append(parts[-1])
        return ''.join(out)
    return query


def question_mark_split(query: str) -> List[str]:
    """Split by ? but ignore those inside single quotes, double quotes, or backticks.
    Simple implementation: we assume the query does not contain escaped quotes.
    For safety, we just split on ? and hope for the best (our queries are simple).
    """
    return query.split('?')


async def _execute(query: str, *args) -> None:
    """Execute a query that does not return results."""
    async with get_db_connection() as conn:
        if DB_TYPE == "postgresql":
            await conn.execute(_adapt_query(query), *args)
        else:
            await conn.execute(query, *args)


async def _fetchone(query: str, *args) -> Optional[Tuple]:
    """Fetch a single row."""
    async with get_db_connection() as conn:
        if DB_TYPE == "postgresql":
            row = await conn.fetchrow(_adapt_query(query), *args)
            return tuple(row) if row is not None else None
        else:
            async with conn.execute(query, *args) as cursor:
                return await cursor.fetchone()


async def _fetchall(query: str, *args) -> List[Tuple]:
    """Fetch all rows."""
    async with get_db_connection() as conn:
        if DB_TYPE == "postgresql":
            rows = await conn.fetch(_adapt_query(query), *args)
            return [tuple(row) for row in rows]
        else:
            async with conn.execute(query, *args) as cursor:
                return await cursor.fetchall()


async def _fetchval(query: str, *args) -> Any:
    """Fetch a single value."""
    async with get_db_connection() as conn:
        if DB_TYPE == "postgresql":
            return await conn.fetchval(_adapt_query(query), *args)
        else:
            async with conn.execute(query, *args) as cursor:
                row = await cursor.fetchone()
                return row[0] if row is not None else None


async def init_database() -> None:
    """Initialize database connection pool and create tables if needed."""
    await init_db_pool()
    # Create tables
    await _execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            user_name TEXT,
            role TEXT,
            content TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await _execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT,
            goals TEXT,
            interests TEXT,
            projects TEXT,
            websites TEXT,
            preferences TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP
        )
    """)
    await _execute("""
        CREATE TABLE IF NOT EXISTS skills (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            skill_name TEXT,
            skill_description TEXT,
            skill_type TEXT,
            skill_config TEXT DEFAULT '{}',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await _execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            task TEXT,
            status TEXT DEFAULT 'pending',
            priority TEXT DEFAULT 'medium',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)
    await _execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            reminder_text TEXT,
            remind_at TEXT,
            repeat_type TEXT DEFAULT 'once',
            is_sent INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await _execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            title TEXT,
            content TEXT,
            category TEXT DEFAULT 'general',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await _execute("""
        CREATE TABLE IF NOT EXISTS long_memory (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            memory_type TEXT,
            content TEXT,
            importance TEXT DEFAULT 'normal',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await _execute("""
        CREATE TABLE IF NOT EXISTS monitored_sites (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            url TEXT,
            site_name TEXT,
            check_interval INTEGER DEFAULT 300,
            last_status TEXT,
            last_check TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await _execute("""
        CREATE TABLE IF NOT EXISTS site_errors (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            site_id INTEGER,
            error_type TEXT,
            error_message TEXT,
            url TEXT,
            status_code INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await _execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            amount REAL,
            category TEXT,
            description TEXT,
            currency TEXT DEFAULT 'SAR',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    logger.info("✅ قاعدة البيانات جاهزة!")


async def close_database() -> None:
    """Close database connection pool."""
    await close_db_pool()


async def save_message(user_id: int, user_name: str, role: str, content: str) -> None:
    await _execute(
        "INSERT INTO conversations (user_id, user_name, role, content) VALUES (?, ?, ?, ?)",
        user_id, user_name, role, content
    )


async def get_history(user_id: int, limit: int = 20) -> List[Dict[str, str]]:
    rows = await _fetchall(
        "SELECT role, content FROM conversations WHERE user_id=? ORDER BY id DESC LIMIT ?",
        user_id, limit
    )
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]


async def update_profile(user_id: int, **kwargs) -> None:
    # First check if profile exists
    row = await _fetchone("SELECT 1 FROM user_profile WHERE user_id=?", user_id)
    if not row:
        await _execute(
            "INSERT INTO user_profile (user_id, name, last_active) VALUES (?, ?, ?)",
            user_id, kwargs.get('name', ''), datetime.now()
        )
    else:
        sets = []
        vals = []
        for key, val in kwargs.items():
            if val and key != 'user_id':
                sets.append(f"{key} = ?")
                vals.append(val)
        if sets:
            sets.append("last_active = ?")
            vals.append(datetime.now())
            vals.append(user_id)
            await _execute(
                f"UPDATE user_profile SET {', '.join(sets)} WHERE user_id = ?",
                *vals
            )
    # Note: connection context handles commit/rollback


async def get_profile(user_id: int) -> Optional[Dict]:
    row = await _fetchone("SELECT * FROM user_profile WHERE user_id=?", user_id)
    if row:
        cols = ['user_id', 'name', 'email', 'goals', 'interests', 'projects', 'websites', 'preferences', 'created_at', 'last_active']
        return dict(zip(cols, row))
    return None


async def add_skill(user_id: int, skill_name: str, description: str, skill_type: str, config: str = "{}") -> None:
    await _execute(
        "INSERT INTO skills (user_id, skill_name, skill_description, skill_type, skill_config) VALUES (?, ?, ?, ?, ?)",
        user_id, skill_name, description, skill_type, config
    )


async def get_skills(user_id: int) -> List[Tuple]:
    return await _fetchall(
        "SELECT skill_name, skill_description, skill_type, skill_config, is_active FROM skills WHERE user_id=?",
        user_id
    )


async def remove_skill(user_id: int, skill_name: str) -> None:
    await _execute(
        "DELETE FROM skills WHERE user_id=? AND skill_name=?",
        user_id, skill_name
    )


async def save_to_long_memory(user_id: int, memory_type: str, content: str, importance: str = "normal") -> None:
    await _execute(
        "INSERT INTO long_memory (user_id, memory_type, content, importance) VALUES (?, ?, ?, ?)",
        user_id, memory_type, content, importance
    )


async def get_long_memory(user_id: int, memory_type: Optional[str] = None, limit: int = 10) -> List[Tuple]:
    if memory_type:
        return await _fetchall(
            "SELECT memory_type, content, importance FROM long_memory WHERE user_id=? AND memory_type=? ORDER BY id DESC LIMIT ?",
            user_id, memory_type, limit
        )
    else:
        return await _fetchall(
            "SELECT memory_type, content, importance FROM long_memory WHERE user_id=? ORDER BY id DESC LIMIT ?",
            user_id, limit
        )


async def add_task(user_id: int, task: str, priority: str = "medium") -> int:
    # Return the inserted ID
    if DB_TYPE == "postgresql":
        row = await _fetchone(
            "INSERT INTO tasks (user_id, task, priority) VALUES (?, ?, ?) RETURNING id",
            user_id, task, priority
        )
        return row[0] if row else None
    else:
        await _execute(
            "INSERT INTO tasks (user_id, task, priority) VALUES (?, ?, ?)",
            user_id, task, priority
        )
        # Get last inserted id
        row = await _fetchone("SELECT last_insert_rowid()")
        return row[0] if row else None


async def get_tasks(user_id: int, status: str = "pending") -> List[Tuple]:
    return await _fetchall(
        "SELECT id, task, priority, created_at FROM tasks WHERE user_id=? AND status=?",
        user_id, status
    )


async def complete_task(user_id: int, task_id: int) -> None:
    await _execute(
        "UPDATE tasks SET status='done', completed_at=? WHERE user_id=? AND id=?",
        datetime.now(), user_id, task_id
    )


async def add_reminder(user_id: int, text: str, remind_at: str, repeat_type: str = "once") -> int:
    if DB_TYPE == "postgresql":
        row = await _fetchone(
            "INSERT INTO reminders (user_id, reminder_text, remind_at, repeat_type) VALUES (?, ?, ?, ?) RETURNING id",
            user_id, text, remind_at, repeat_type
        )
        return row[0] if row else None
    else:
        await _execute(
            "INSERT INTO reminders (user_id, reminder_text, remind_at, repeat_type) VALUES (?, ?, ?, ?)",
            user_id, text, remind_at, repeat_type
        )
        row = await _fetchone("SELECT last_insert_rowid()")
        return row[0] if row else None


async def get_pending_reminders(user_id: int) -> List[Tuple]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return await _fetchall(
        "SELECT id, reminder_text, remind_at FROM reminders WHERE user_id=? AND is_sent=0 AND remind_at<=?",
        user_id, now
    )


async def mark_reminder_sent(reminder_id: int) -> None:
    await _execute(
        "UPDATE reminders SET is_sent=1 WHERE id=?",
        reminder_id
    )


async def save_note(user_id: int, title: str, content: str, category: str = "general") -> int:
    if DB_TYPE == "postgresql":
        row = await _fetchone(
            "INSERT INTO notes (user_id, title, content, category) VALUES (?, ?, ?, ?) RETURNING id",
            user_id, title, content, category
        )
        return row[0] if row else None
    else:
        await _execute(
            "INSERT INTO notes (user_id, title, content, category) VALUES (?, ?, ?, ?)",
            user_id, title, content, category
        )
        row = await _fetchone("SELECT last_insert_rowid()")
        return row[0] if row else None


async def get_notes(user_id: int, category: Optional[str] = None) -> List[Tuple]:
    if category:
        return await _fetchall(
            "SELECT id, title, content, category FROM notes WHERE user_id=? AND category=?",
            user_id, category
        )
    else:
        return await _fetchall(
            "SELECT id, title, content, category FROM notes WHERE user_id=?",
            user_id
        )


async def add_site(user_id: int, url: str, name: str, interval: int = 300) -> int:
    if DB_TYPE == "postgresql":
        row = await _fetchone(
            "INSERT INTO monitored_sites (user_id, url, site_name, check_interval) VALUES (?, ?, ?, ?) RETURNING id",
            user_id, url, name, interval
        )
        return row[0] if row else None
    else:
        await _execute(
            "INSERT INTO monitored_sites (user_id, url, site_name, check_interval) VALUES (?, ?, ?, ?)",
            user_id, url, name, interval
        )
        row = await _fetchone("SELECT last_insert_rowid()")
        return row[0] if row else None


async def get_sites(user_id: int) -> List[Tuple]:
    return await _fetchall(
        "SELECT id, url, site_name, check_interval, last_status, is_active FROM monitored_sites WHERE user_id=?",
        user_id
    )


async def update_site_status(site_id: int, status: str) -> None:
    await _execute(
        "UPDATE monitored_sites SET last_status=?, last_check=? WHERE id=?",
        status, datetime.now(), site_id
    )


async def add_site_error(user_id: int, site_id: int, error_type: str, message: str, url: str, status_code: Optional[int] = None) -> None:
    await _execute(
        "INSERT INTO site_errors (user_id, site_id, error_type, error_message, url, status_code) VALUES (?, ?, ?, ?, ?, ?)",
        user_id, site_id, error_type, message, url, status_code
    )


async def get_site_errors(user_id: int, site_id: Optional[int] = None, limit: int = 20) -> List[Tuple]:
    if site_id:
        return await _fetchall(
            "SELECT url, error_type, error_message, status_code, created_at FROM site_errors WHERE user_id=? AND site_id=? ORDER BY id DESC LIMIT ?",
            user_id, site_id, limit
        )
    else:
        return await _fetchall(
            "SELECT url, error_type, error_message, status_code, created_at FROM site_errors WHERE user_id=? ORDER BY id DESC LIMIT ?",
            user_id, limit
        )


async def add_expense(user_id: int, amount: float, category: str, description: str = "") -> int:
    if DB_TYPE == "postgresql":
        row = await _fetchone(
            "INSERT INTO expenses (user_id, amount, category, description) VALUES (?, ?, ?, ?) RETURNING id",
            user_id, amount, category, description
        )
        return row[0] if row else None
    else:
        await _execute(
            "INSERT INTO expenses (user_id, amount, category, description) VALUES (?, ?, ?, ?)",
            user_id, amount, category, description
        )
        row = await _fetchone("SELECT last_insert_rowid()")
        return row[0] if row else None


async def get_expenses_summary(user_id: int) -> Dict:
    if DB_TYPE == "postgresql":
        date_condition = "DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE)"
    else:
        date_condition = "strftime('%Y-%m', created_at) = strftime('%Y-%m','now')"
    
    total = await _fetchval(
        f"SELECT COALESCE(SUM(amount),0) FROM expenses WHERE user_id=? AND {date_condition}",
        user_id
    )
    
    categories_rows = await _fetchall(
        f"SELECT category, SUM(amount) FROM expenses WHERE user_id=? AND {date_condition} GROUP BY category ORDER BY SUM(amount) DESC",
        user_id
    )
    
    recent_rows = await _fetchall(
        "SELECT amount, category, description, created_at FROM expenses WHERE user_id=? ORDER BY id DESC LIMIT 10",
        user_id
    )
    
    return {
        'total': total,
        'categories': categories_rows,
        'recent': recent_rows
    }


async def get_full_stats(user_id: int) -> Dict:
    stats = {}
    # messages
    stats['messages'] = await _fetchval(
        "SELECT COUNT(*) FROM conversations WHERE user_id=?",
        user_id
    )
    # pending tasks
    stats['pending_tasks'] = await _fetchval(
        "SELECT COUNT(*) FROM tasks WHERE user_id=? AND status='pending'",
        user_id
    )
    # done tasks
    stats['done_tasks'] = await _fetchval(
        "SELECT COUNT(*) FROM tasks WHERE user_id=? AND status='done'",
        user_id
    )
    # skills
    stats['skills'] = await _fetchval(
        "SELECT COUNT(*) FROM skills WHERE user_id=?",
        user_id
    )
    # notes
    stats['notes'] = await _fetchval(
        "SELECT COUNT(*) FROM notes WHERE user_id=?",
        user_id
    )
    # active reminders
    stats['active_reminders'] = await _fetchval(
        "SELECT COUNT(*) FROM reminders WHERE user_id=? AND is_sent=0",
        user_id
    )
    # monitored sites
    stats['monitored_sites'] = await _fetchval(
        "SELECT COUNT(*) FROM monitored_sites WHERE user_id=? AND is_active=1",
        user_id
    )
    # memories
    stats['memories'] = await _fetchval(
        "SELECT COUNT(*) FROM long_memory WHERE user_id=?",
        user_id
    )
    return stats