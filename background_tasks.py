# ═══════════════════════════════════════════
# المهمة الخلفية التلقائية
# ═══════════════════════════════════════════
import asyncio
import aiosqlite
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

# معرف المالك (يُحفظ تلقائي عند أول محادثة)
OWNER_ID = None
OWNER_NAME = None


async def set_owner(user_id, user_name):
    """حفظ معرف المالك"""
    global OWNER_ID, OWNER_NAME
    OWNER_ID = user_id
    OWNER_NAME = user_name
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute(
            "INSERT OR REPLACE INTO bot_config (key, value) VALUES (?, ?)",
            ("owner_id", str(user_id))
        )
        await db.execute(
            "INSERT OR REPLACE INTO bot_config (key, value) VALUES (?, ?)",
            ("owner_name", str(user_name))
        )
        await db.commit()
    print(f"👤 المالك: {user_name} (ID: {user_id})")


async def get_owner():
    """جلب معرف المالك"""
    global OWNER_ID, OWNER_NAME
    if OWNER_ID:
        return OWNER_ID, OWNER_NAME

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT value FROM bot_config WHERE key='owner_id'"
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    OWNER_ID = int(row[0])

            async with db.execute(
                "SELECT value FROM bot_config WHERE key='owner_name'"
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    OWNER_NAME = row[0]

        return OWNER_ID, OWNER_NAME
    except:
        return None, None


# ═══════════════════════════════════════════
# مهمة التذكيرات (كل دقيقة)
# ═══════════════════════════════════════════
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
            print(f"🔔 تم إرسال تذكير: {text}")

    except Exception as e:
        print(f"❌ خطأ التذكيرات: {e}")


# ═══════════════════════════════════════════
# مهمة مراقبة المواقع (كل 5 دقائق)
# ═══════════════════════════════════════════
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
                print(f"🚨 تنبيه: {result['site']} - {result['message']}")

    except Exception as e:
        print(f"❌ خطأ المراقبة: {e}")


# ═══════════════════════════════════════════
# مهمة التقرير اليومي (كل يوم الساعة 8)
# ═══════════════════════════════════════════
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

═══════════════════════════

💬 الرسائل: {stats['messages']}
📋 مهام معلقة: {stats['pending_tasks']}
✅ مهام منجزة: {stats['done_tasks']}
🧠 مهارات: {stats['skills']}
📝 ملاحظات: {stats['notes']}
🌐 مواقع مراقبة: {stats['monitored_sites']}
💾 ذكريات: {stats['memories']}

═══════════════════════════
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

        report += "═══════════════════════════\n"
        report += f"🤖 {AGENT_NAME} - يوم جديد مليء إنجازات! 💪"

        await bot.send_message(
            chat_id=user_id,
            text=report,
            parse_mode='Markdown'
        )
        print(f"📊 تم إرسال التقرير اليومي لـ {user_name}")

    except Exception as e:
        print(f"❌ خطأ التقرير: {e}")


# ═══════════════════════════════════════════
# مهمة تذكير المهام (كل يوم الساعة 9)
# ═══════════════════════════════════════════
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
        print(f"📋 تم إرسال تذكير المهام")

    except Exception as e:
        print(f"❌ خطأ تذكير المهام: {e}")


# ═══════════════════════════════════════════
# مهمة التقرير الأسبوعي (كل أسبوع)
# ═══════════════════════════════════════════
async def send_weekly_report(bot):
    """تقرير أسبوعي شامل"""
    user_id, user_name = await get_owner()
    if not user_id:
        return

    try:
        stats = await get_full_stats(user_id)
        expenses = await get_expenses_summary(user_id)

        msg = f"""📊 **التقرير الأسبوعي - {user_name}**
═══════════════════════════

📈 **ملخص الأسبوع:**

💬 إجمالي الرسائل: {stats['messages']}
📋 مهام معلقة: {stats['pending_tasks']}
✅ مهام منجزة: {stats['done_tasks']}
🧠 مهارات متعلمة: {stats['skills']}
📝 ملاحظات: {stats['notes']}
🌐 مواقع مراقبة: {stats['monitored_sites']}

═══════════════════════════

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
═══════════════════════════

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
        print(f"📊 تم إرسال التقرير الأسبوعي")

    except Exception as e:
        print(f"❌ خطأ التقرير الأسبوعي: {e}")


# ═══════════════════════════════════════════
# المهمة الرئيسية (تشتغل كل شي)
# ═══════════════════════════════════════════
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

    print("=" * 60)
    print("🔄 المهمة الخلفية التلقائية شغّالة!")
    print("📋 التذكيرات: كل دقيقة")
    print("🌐 المواقع: كل 5 دقائق")
    print("📊 التقرير اليومي: الساعة 8 صباحاً")
    print("📋 تذكير المهام: الساعة 9 صباحاً")
    print("📊 التقرير الأسبوعي: الأحد الساعة 10 صباحاً")
    print("=" * 60)

    while True:
        try:
            now = datetime.now()
            minute_counter += 1

            # ═══════════════════════════
            # كل دقيقة: فحص التذكيرات
            # ═══════════════════════════
            if minute_counter % 1 == 0:
                await check_reminders(bot)

            # ═══════════════════════════
            # كل 5 دقائق: فحص المواقع
            # ═══════════════════════════
            if minute_counter % 5 == 0:
                await check_sites(bot)

            # ═══════════════════════════
            # كل يوم الساعة 8: التقرير اليومي
            # ═══════════════════════════
            today = now.strftime("%Y-%m-%d")
            if now.hour == 8 and now.minute == 0:
                if last_daily_report != today:
                    await send_daily_report(bot)
                    last_daily_report = today

            # ═══════════════════════════
            # كل يوم الساعة 9: تذكير المهام
            # ═══════════════════════════
            if now.hour == 9 and now.minute == 0:
                if last_tasks_reminder != today:
                    await send_tasks_reminder(bot)
                    last_tasks_reminder = today

            # ═══════════════════════════
            # الأحد الساعة 10: التقرير الأسبوعي
            # ═══════════════════════════
            if now.weekday() == 6 and now.hour == 10 and now.minute == 0:
                week_key = now.strftime("%Y-W%W")
                if last_weekly_report != week_key:
                    await send_weekly_report(bot)
                    last_weekly_report = week_key

        except Exception as e:
            print(f"❌ خطأ في المهمة الخلفية: {e}")

        # انتظار دقيقة
        await asyncio.sleep(60)