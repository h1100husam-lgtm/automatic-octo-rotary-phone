# ════════════════════════════════════════════
# المهمة الخلفية التلقائية
# ════════════════════════════════════════════
import asyncio
import logging
from datetime import datetime, timedelta
from config import DB_PATH, AGENT_NAME
from memory import (
    get_pending_reminders, mark_reminder_sent,
    get_tasks, get_full_stats, get_site_errors,
    get_expenses_summary
)
from site_monitor import check_site, monitor_all_sites
from email_reports import generate_daily_report
from email_sender import EmailSender

logger = logging.getLogger("agent.background")

# معرف المالك (يُحفظ تلقائيًا عند أول محادثة)
OWNER_ID = None
OWNER_NAME = None

# Database pool imports
from db_pool import get_db_connection
from config import DB_TYPE

# Helper functions to handle both SQLite and PostgreSQL
async def _execute(query: str, *args) -> None:
    """Execute a query that does not return results."""
    async with get_db_connection() as conn:
        if DB_TYPE == "postgresql":
            await conn.execute(_adapt_query(query), *args)
        else:
            await conn.execute(query, *args)
            await conn.commit()


async def _fetchone(query: str, *args):
    """Fetch a single row."""
    async with get_db_connection() as conn:
        if DB_TYPE == "postgresql":
            row = await conn.fetchrow(_adapt_query(query), *args)
            return tuple(row) if row is not None else None
        else:
            async with conn.execute(query, *args) as cursor:
                return await cursor.fetchone()


async def _fetchall(query: str, *args):
    """Fetch all rows."""
    async with get_db_connection() as conn:
        if DB_TYPE == "postgresql":
            rows = await conn.fetch(_adapt_query(query), *args)
            return [tuple(row) for row in rows]
        else:
            async with conn.execute(query, *args) as cursor:
                return await cursor.fetchall()


async def _fetchval(query: str, *args):
    """Fetch a single value."""
    async with get_db_connection() as conn:
        if DB_TYPE == "postgresql":
            return await conn.fetchval(_adapt_query(query), *args)
        else:
            async with conn.execute(query, *args) as cursor:
                row = await cursor.fetchone()
                return row[0] if row is not None else None


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


def question_mark_split(query: str) -> list:
    """Split by ? but ignore those inside single quotes, double quotes, or backticks.
    Simple implementation: we assume the query does not contain escaped quotes.
    For safety, we just split on ? and hope for the best (our queries are simple).
    """
    return query.split('?')


async def set_owner(user_id, user_name):
    """حفظ معرف المالك"""
    global OWNER_ID, OWNER_NAME
    OWNER_ID = user_id
    OWNER_NAME = user_name
    async with get_db_connection() as conn:
        # Ensure table exists
        if DB_TYPE == "postgresql":
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS bot_config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
        else:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS bot_config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            await conn.commit()
        # Insert or replace owner_id and owner_name
        if DB_TYPE == "postgresql":
            await conn.execute(
                "INSERT INTO bot_config (key, value) VALUES ($1, $2) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                "owner_id", str(user_id)
            )
            await conn.execute(
                "INSERT INTO bot_config (key, value) VALUES ($1, $2) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                "owner_name", str(user_name)
            )
        else:
            await conn.execute(
                "INSERT OR REPLACE INTO bot_config (key, value) VALUES (?, ?)",
                ("owner_id", str(user_id))
            )
            await conn.execute(
                "INSERT OR REPLACE INTO bot_config (key, value) VALUES (?, ?)",
                ("owner_name", str(user_name))
            )
            await conn.commit()
    logger.info(f"👤 المالك: {user_name} (ID: {user_id})")


async def get_owner():
    """جلب معرف المالك"""
    global OWNER_ID, OWNER_NAME
    if OWNER_ID:
        return OWNER_ID, OWNER_NAME

    try:
        async with get_db_connection() as conn:
            # Ensure table exists (should already)
            if DB_TYPE == "postgresql":
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS bot_config (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
            else:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS bot_config (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
                await conn.commit()
            # Get owner_id
            row = await _fetchone("SELECT value FROM bot_config WHERE key='owner_id'")
            if row:
                OWNER_ID = int(row[0])
            # Get owner_name
            row = await _fetchone("SELECT value FROM bot_config WHERE key='owner_name'")
            if row:
                OWNER_NAME = row[0]
    except Exception:
        pass
    return OWNER_ID, OWNER_NAME


# ════════════════════════════════════════════
# مهمة التذكيرات (كل دقيقة)
# ════════════════════════════════════════════
async def check_reminders(bot):
    """فحص وإرسال التذكيرات"""
    user_id, user_name = await get_owner()
    if not user_id:
        return

    try:
        reminders = await get_pending_reminders(user_id)

        for reminder in reminders:
            rem_id, text, remind_at = reminder

            # إرسال التذكير
            await bot.send_message(
                chat_id=user_id,
                text=f"🔔 **تذكير!**\n\n📝 {text}\n⏰ {remind_at}",
                parse_mode='Markdown'
            )

            # تعليم كمرسل
            await mark_reminder_sent(rem_id)
            logger.info(f"🔔 تذكير أُرسل: {text}")

    except Exception as e:
        logger.error(f"خطأ التذكيرات: {e}")


# ════════════════════════════════════════════
# مهمة مراقبة المواقع (كل 5 دقائق)
# ════════════════════════════════════════════
async def check_sites(bot):
    """فحص المواقع وإرسال التنبيهات"""
    user_id, user_name = await get_owner()
    if not user_id:
        return

    try:
        results = await monitor_all_sites(user_id)

        for result in results:
            if result.get('alert'):
                # إرسال تنبيه فوري
                await bot.send_message(
                    chat_id=user_id,
                    text=f"""🚨 **تنبيه موقع!**

🌐 الموقع: {result['site']}
🔗 الرابط: {result['url']}
⚠️ المشكلة: {result['message']}

💡 افحص الموقع فوراً!""",
                    parse_mode='Markdown'
                )
                logger.warning(f"تنبيه موقع: {result['site']} - {result['message']}")

    except Exception as e:
        logger.error(f"خطأ المراقبة: {e}")


# ════════════════════════════════════════════
# مهمة التقرير اليومي (كل يوم الساعة 8)
# ════════════════════════════════════════════
async def send_daily_report(bot):
    """إرسال التقرير اليومي"""
    user_id, user_name = await get_owner()
    if not user_id:
        return

    try:
        stats = await get_full_stats(user_id)
        pending = await get_tasks(user_id, "pending")
        errors = await get_site_errors(user_id, limit=5)

        now = datetime.now()
        report = f"""📊 **صباح الخير {user_name}!**
تقريرك اليومي - {now.strftime('%Y-%m-%d')}

════════════════════════════════════════════

💬 الرسائل: {stats['messages']}
📋 مهام معلقة: {stats['pending_tasks']}
✅ مهام منجزة: {stats['done_tasks']}
🧠 مهارات: {stats['skills']}
📝 ملاحظات: {stats['notes']}
🌐 مواقع مراقبة: {stats['monitored_sites']}
💾 ذكريات: {stats['memories']}

════════════════════════════════════════════
"""

        if pending:
            report += "📋 **المهام المعلقة:**\n"
            for t in pending[:10]:
                p = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(t[2], "🟡")
                report += f"  {p} {t[1]}\n"
            report += "\n"

        if errors:
            report += "⚠️ **آخر أخطاء المواقع:**\n"
            for e in errors[:5]:
                report += f"  ❌ {e[0]} - {str(e[2])[:60]}\n"
            report += "\n"

        report += "═══════════════════════════════════════════\n"
        report += f"🤖 {AGENT_NAME} - يوم جديد مليء إنجازات! 💪"

        await bot.send_message(
            chat_id=user_id,
            text=report,
            parse_mode='Markdown'
        )
        logger.info(f"📊 تقرير يومي أُرسل لـ {user_name}")

    except Exception as e:
        logger.error(f"خطأ التقرير: {e}")


# ════════════════════════════════════════════
# مهمة تذكير المهام (كل يوم الساعة 9)
# ════════════════════════════════════════════
async def send_tasks_reminder(bot):
    """تذكير بالمهام المعلقة"""
    user_id, user_name = await get_owner()
    if not user_id:
        return

    try:
        pending = await get_tasks(user_id, "pending")

        if not pending:
            return

        msg = f"📋 **{user_name}، عندك {len(pending)} مهمة معلقة:**\n\n"

        for t in pending[:10]:
            p = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(t[2], "🟡")
            msg += f"{p} {t[1]}\n"

        msg += f"\n💪 خلنا ننجز اليوم!"
        msg += f"\n\n✅ إنهاء: /donetask رقم"

        await bot.send_message(
            chat_id=user_id,
            text=msg,
            parse_mode='Markdown'
        )
        logger.info("📋 تذكير المهام أُرسل")

    except Exception as e:
        logger.error(f"خطأ تذكير المهام: {e}")


# ════════════════════════════════════════════
# مهمة التقرير الأسبوعي (كل أسبوع)
# ════════════════════════════════════════════
async def send_weekly_report(bot):
    """تقرير أسبوعي شامل"""
    user_id, user_name = await get_owner()
    if not user_id:
        return

    try:
        stats = await get_full_stats(user_id)
        expenses = await get_expenses_summary(user_id)

        msg = f"""📊 **التقرير الأسبوعي - {user_name}**
════════════════════════════════════════════

📈 **ملخص الأسبوع:**

💬 إجمالي الرسائل: {stats['messages']}
📋 مهام معلقة: {stats['pending_tasks']}
✅ مهام منجزة: {stats['done_tasks']}
🧠 مهارات متعلمة: {stats['skills']}
📝 ملاحظات: {stats['notes']}
🌐 مواقع مراقبة: {stats['monitored_sites']}

════════════════════════════════════════════

💰 **المصاريف هذا الشهر:**
📊 الإجمالي: {expenses['total']:.2f} ريال

"""

        if expenses['categories']:
            for cat in expenses['categories']:
                msg += f"  💸 {cat[0]}: {cat[1]:.2f} ريال\n"

        # تقييم الأداء
        completion_rate = 0
        if stats['pending_tasks'] + stats['done_tasks'] > 0:
            completion_rate = stats['done_tasks'] / (stats['pending_tasks'] + stats['done_tasks']) * 100

        msg += f"""
════════════════════════════════════════════

📊 **تقييم الأداء:**
✅ نسبة إنجاز المهام: {completion_rate:.0f}%
"""

        if completion_rate >= 80:
            msg += "🏆 أداء ممتاز! استمر!"
        elif completion_rate >= 50:
            msg += "👍 أداء جيد، حاول تحسّن أكثر!"
        else:
            msg += "💪 تحتاج تركّز أكثر، أقدر أساعدك!"

        msg += f"\n\n🤖 {AGENT_NAME} - أنت أفضل من الأمس! 🚀"

        await bot.send_message(
            chat_id=user_id,
            text=msg,
            parse_mode='Markdown'
        )
        logger.info("📊 تقرير أسبوعي أُرسل")

    except Exception as e:
        logger.error(f"خطأ التقرير الأسبوعي: {e}")


# ════════════════════════════════════════════
# المهمة الرئيسية (تشتغل كل شي)
# ════════════════════════════════════════════
async def background_scheduler(bot):
    """الجدول الزمني للمهام الخلفية"""
    await asyncio.sleep(15)  # انتظار بعد التشغيل

    # جلب المالك
    await get_owner()

    # عداد الدقائق
    minute_counter = 0
    last_daily_report = None
    last_tasks_reminder = None
    last_weekly_report = None

    logger.info("=" * 60)
    logger.info("🔄 المهمة الخلفية التلقائية شغّالة!")
    logger.info("📋 التذكيرات: كل دقيقة")
    logger.info("🌐 المواقع: كل 5 دقائق")
    logger.info("📊 التقرير اليومي: الساعة 8 صباحاً")
    logger.info("📋 تذكير المهام: الساعة 9 صباحاً")
    logger.info("📊 التقرير الأسبوعي: الأحد الساعة 10 صباحاً")
    logger.info("=" * 60)

    while True:
        try:
            now = datetime.now()
            minute_counter += 1

            # ═════════════════════════════════════════
            # كل دقيقة: فحص التذكيرات
            # ════════════════════════════════════════
            if minute_counter % 1 == 0:
                await check_reminders(bot)

            # ════════════════════════════════════════
            # كل 5 دقائق: فحص المواقع
            # ════════════════════════════════════════
            if minute_counter % 5 == 0:
                await check_sites(bot)

            # ════════════════════════════════════════
            # كل يوم الساعة 8: التقرير اليومي
            # ════════════════════════════════════════
            if now.hour == 8 and now.minute == 0:
                today = now.strftime("%Y-%m-%d")
                if last_daily_report != today:
                    await send_daily_report(bot)
                    last_daily_report = today

            # ════════════════════════════════════════
            # كل يوم الساعة 9: تذكير المهام
            # ════════════════════════════════════════
            if now.hour == 9 and now.minute == 0:
                today = now.strftime("%Y-%m-%d")
                if last_tasks_reminder != today:
                    await send_tasks_reminder(bot)
                    last_tasks_reminder = today

            # ════════════════════════════════════════
            # الأحد الساعة 10: التقرير الأسبوعي
            # ════════════════════════════════════════
            if now.weekday() == 6 and now.hour == 10 and now.minute == 0:
                week_key = now.strftime("%Y-W%W")
                if last_weekly_report != week_key:
                    await send_weekly_report(bot)
                    last_weekly_report = week_key

        except Exception as e:
            logger.error(f"خطأ في المهمة الخلفية: {e}")

        # انتظار دقيقة
        await asyncio.sleep(60)