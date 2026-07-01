# ═══════════════════════════════════════════
# نظام الذاكرة وقاعدة البيانات
# ═══════════════════════════════════════════
import aiosqlite
from datetime import datetime
from config import DB_PATH


async def init_database():
    """إنشاء كل الجداول"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                user_name TEXT,
                role TEXT,
                content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                user_id INTEGER PRIMARY KEY,
                name TEXT,
                email TEXT,
                goals TEXT,
                interests TEXT,
                projects TEXT,
                websites TEXT,
                preferences TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_active DATETIME
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                skill_name TEXT,
                skill_description TEXT,
                skill_type TEXT,
                skill_config TEXT DEFAULT '{}',
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                task TEXT,
                status TEXT DEFAULT 'pending',
                priority TEXT DEFAULT 'medium',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                reminder_text TEXT,
                remind_at TEXT,
                repeat_type TEXT DEFAULT 'once',
                is_sent INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT,
                content TEXT,
                category TEXT DEFAULT 'general',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS long_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                memory_type TEXT,
                content TEXT,
                importance TEXT DEFAULT 'normal',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS monitored_sites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                url TEXT,
                site_name TEXT,
                check_interval INTEGER DEFAULT 300,
                last_status TEXT,
                last_check DATETIME,
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS site_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                site_id INTEGER,
                error_type TEXT,
                error_message TEXT,
                url TEXT,
                status_code INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                category TEXT,
                description TEXT,
                currency TEXT DEFAULT 'SAR',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
    print("✅ قاعدة البيانات جاهزة!")


# ═══════════════════════════════
# المحادثات
# ═══════════════════════════════
async def save_message(user_id, user_name, role, content):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO conversations (user_id, user_name, role, content) VALUES (?,?,?,?)",
            (user_id, user_name, role, content)
        )
        await db.commit()


async def get_history(user_id, limit=20):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT role, content FROM conversations WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [{"role": r[0], "content": r[1]} for r in reversed(rows)]


# ═══════════════════════════════
# الملف الشخصي
# ═══════════════════════════════
async def update_profile(user_id, **kwargs):
    async with aiosqlite.connect(DB_PATH) as db:
        existing = await get_profile(user_id)
        if not existing:
            await db.execute(
                "INSERT INTO user_profile (user_id, name, last_active) VALUES (?,?,?)",
                (user_id, kwargs.get('name', ''), datetime.now())
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
                await db.execute(
                    f"UPDATE user_profile SET {', '.join(sets)} WHERE user_id = ?",
                    vals
                )
        await db.commit()


async def get_profile(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM user_profile WHERE user_id=?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                cols = ['user_id', 'name', 'email', 'goals', 'interests',
                        'projects', 'websites', 'preferences', 'created_at', 'last_active']
                return dict(zip(cols, row))
            return None


# ═══════════════════════════════
# المهارات
# ═══════════════════════════════
async def add_skill(user_id, skill_name, description, skill_type, config="{}"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO skills (user_id, skill_name, skill_description, skill_type, skill_config) VALUES (?,?,?,?,?)",
            (user_id, skill_name, description, skill_type, config)
        )
        await db.commit()


async def get_skills(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT skill_name, skill_description, skill_type, skill_config, is_active FROM skills WHERE user_id=?",
            (user_id,)
        ) as cursor:
            return await cursor.fetchall()


async def remove_skill(user_id, skill_name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM skills WHERE user_id=? AND skill_name=?",
            (user_id, skill_name)
        )
        await db.commit()


# ═══════════════════════════════
# الذاكرة طويلة المدى
# ═══════════════════════════════
async def save_to_long_memory(user_id, memory_type, content, importance="normal"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO long_memory (user_id, memory_type, content, importance) VALUES (?,?,?,?)",
            (user_id, memory_type, content, importance)
        )
        await db.commit()


async def get_long_memory(user_id, memory_type=None, limit=10):
    async with aiosqlite.connect(DB_PATH) as db:
        if memory_type:
            async with db.execute(
                "SELECT memory_type, content, importance FROM long_memory WHERE user_id=? AND memory_type=? ORDER BY id DESC LIMIT ?",
                (user_id, memory_type, limit)
            ) as cursor:
                return await cursor.fetchall()
        else:
            async with db.execute(
                "SELECT memory_type, content, importance FROM long_memory WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, limit)
            ) as cursor:
                return await cursor.fetchall()


# ═══════════════════════════════
# المهام
# ═══════════════════════════════
async def add_task(user_id, task, priority="medium"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO tasks (user_id, task, priority) VALUES (?,?,?)",
            (user_id, task, priority)
        )
        await db.commit()


async def get_tasks(user_id, status="pending"):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, task, priority, created_at FROM tasks WHERE user_id=? AND status=?",
            (user_id, status)
        ) as cursor:
            return await cursor.fetchall()


async def complete_task(user_id, task_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tasks SET status='done', completed_at=? WHERE user_id=? AND id=?",
            (datetime.now(), user_id, task_id)
        )
        await db.commit()


# ═══════════════════════════════
# التذكيرات
# ═══════════════════════════════
async def add_reminder(user_id, text, remind_at, repeat_type="once"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO reminders (user_id, reminder_text, remind_at, repeat_type) VALUES (?,?,?,?)",
            (user_id, text, remind_at, repeat_type)
        )
        await db.commit()


async def get_pending_reminders(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        async with db.execute(
            "SELECT id, reminder_text, remind_at FROM reminders WHERE user_id=? AND is_sent=0 AND remind_at<=?",
            (user_id, now)
        ) as cursor:
            return await cursor.fetchall()


async def mark_reminder_sent(reminder_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE reminders SET is_sent=1 WHERE id=?", (reminder_id,))
        await db.commit()


# ═══════════════════════════════
# الملاحظات
# ═══════════════════════════════
async def save_note(user_id, title, content, category="general"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO notes (user_id, title, content, category) VALUES (?,?,?,?)",
            (user_id, title, content, category)
        )
        await db.commit()


async def get_notes(user_id, category=None):
    async with aiosqlite.connect(DB_PATH) as db:
        if category:
            async with db.execute(
                "SELECT id, title, content, category FROM notes WHERE user_id=? AND category=?",
                (user_id, category)
            ) as cursor:
                return await cursor.fetchall()
        else:
            async with db.execute(
                "SELECT id, title, content, category FROM notes WHERE user_id=?",
                (user_id,)
            ) as cursor:
                return await cursor.fetchall()


# ═══════════════════════════════
# المواقع
# ═══════════════════════════════
async def add_site(user_id, url, name, interval=300):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO monitored_sites (user_id, url, site_name, check_interval) VALUES (?,?,?,?)",
            (user_id, url, name, interval)
        )
        await db.commit()


async def get_sites(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, url, site_name, check_interval, last_status, is_active FROM monitored_sites WHERE user_id=?",
            (user_id,)
        ) as cursor:
            return await cursor.fetchall()


async def update_site_status(site_id, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE monitored_sites SET last_status=?, last_check=? WHERE id=?",
            (status, datetime.now(), site_id)
        )
        await db.commit()


async def add_site_error(user_id, site_id, error_type, message, url, status_code=None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO site_errors (user_id, site_id, error_type, error_message, url, status_code) VALUES (?,?,?,?,?,?)",
            (user_id, site_id, error_type, message, url, status_code)
        )
        await db.commit()


async def get_site_errors(user_id, site_id=None, limit=20):
    async with aiosqlite.connect(DB_PATH) as db:
        if site_id:
            async with db.execute(
                "SELECT url, error_type, error_message, status_code, created_at FROM site_errors WHERE user_id=? AND site_id=? ORDER BY id DESC LIMIT ?",
                (user_id, site_id, limit)
            ) as cursor:
                return await cursor.fetchall()
        else:
            async with db.execute(
                "SELECT url, error_type, error_message, status_code, created_at FROM site_errors WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, limit)
            ) as cursor:
                return await cursor.fetchall()


# ═══════════════════════════════
# المصاريف
# ═══════════════════════════════
async def add_expense(user_id, amount, category, description=""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO expenses (user_id, amount, category, description) VALUES (?,?,?,?)",
            (user_id, amount, category, description)
        )
        await db.commit()


async def get_expenses_summary(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COALESCE(SUM(amount),0) FROM expenses WHERE user_id=? AND strftime('%Y-%m', created_at)=strftime('%Y-%m','now')",
            (user_id,)
        ) as cursor:
            total = (await cursor.fetchone())[0]

        async with db.execute(
            "SELECT category, SUM(amount) FROM expenses WHERE user_id=? AND strftime('%Y-%m', created_at)=strftime('%Y-%m','now') GROUP BY category ORDER BY SUM(amount) DESC",
            (user_id,)
        ) as cursor:
            categories = await cursor.fetchall()

        async with db.execute(
            "SELECT amount, category, description, created_at FROM expenses WHERE user_id=? ORDER BY id DESC LIMIT 10",
            (user_id,)
        ) as cursor:
            recent = await cursor.fetchall()

        return {'total': total, 'categories': categories, 'recent': recent}


# ═══════════════════════════════
# الإحصائيات
# ═══════════════════════════════
async def get_full_stats(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        stats = {}

        async with db.execute("SELECT COUNT(*) FROM conversations WHERE user_id=?", (user_id,)) as c:
            stats['messages'] = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM tasks WHERE user_id=? AND status='pending'", (user_id,)) as c:
            stats['pending_tasks'] = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM tasks WHERE user_id=? AND status='done'", (user_id,)) as c:
            stats['done_tasks'] = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM skills WHERE user_id=?", (user_id,)) as c:
            stats['skills'] = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM notes WHERE user_id=?", (user_id,)) as c:
            stats['notes'] = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM reminders WHERE user_id=? AND is_sent=0", (user_id,)) as c:
            stats['active_reminders'] = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM monitored_sites WHERE user_id=?", (user_id,)) as c:
            stats['monitored_sites'] = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM long_memory WHERE user_id=?", (user_id,)) as c:
            stats['memories'] = (await c.fetchone())[0]

        return stats