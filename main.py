# ═══════════════════════════════════════════
# Agent v5.0 - النهائي للسيرفر
# ═══════════════════════════════════════════
import asyncio
import os
from telegram import Update
from telegram.ext import (
    Application, MessageHandler, CommandHandler,
    filters, ContextTypes
)

from config import TELEGRAM_TOKEN, AGENT_NAME
from memory import (
    init_database, save_message, update_profile, get_profile,
    add_task, get_tasks, complete_task, save_note, get_notes,
    add_site, get_sites, get_full_stats, get_skills,
    add_expense, get_expenses_summary
)
from ai_engine import get_smart_reply
from skill_executor import parse_and_execute
from site_monitor import check_site
from email_reports import generate_daily_report
from email_sender import EmailSender
from web_search import search_and_format
from code_runner import execute_python_code, format_code_result
from image_handler import analyze_image
from site_fixer import deep_check_site, format_site_report
from utils import generate_password, generate_qr, shorten_url
from self_builder import (
    init_self_builder, build_feature,
    get_all_features, execute_feature
)
from background_tasks import background_scheduler, set_owner

email_service = EmailSender()


# ═══════════════════════════════════════
# /start
# ═══════════════════════════════════════
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await set_owner(user.id, user.first_name)
    await update_profile(user.id, name=user.first_name)

    await update.message.reply_text(f"""🤖 أهلاً {user.first_name}!
أنا {AGENT_NAME} - مساعدك الشخصي الخارق 🧠

🎯 **قدراتي:**

🧠 ذكاء:
/search - بحث في الإنترنت
/code - تنفيذ أكواد Python

📋 إنتاجية:
/addtask - إضافة مهمة
/tasks - مهامك
/donetask - إنهاء مهمة
/note - ملاحظة
/mynotes - ملاحظاتك

💰 مالية:
/spent - تسجيل مصروف
/expenses - تقرير مصاريف

🌐 مراقبة:
/addsite - مراقبة موقع
/checksite - فحص موقع
/deepcheck - فحص عميق

📧 تقارير:
/setemail - إعداد الإيميل
/report - تقرير شامل

🛠️ أدوات:
/password - كلمة مرور
/qr - توليد QR
/shorturl - تقصير رابط

🔧 البناء الذاتي:
/build - بناء ميزة جديدة
/run - تشغيل ميزة
/features - ميزاتي المبنية

📊 النظام:
/skills - مهاراتي
/stats - إحصائيات
/profile - ملفك

🖼️ أرسل صورة = أحللها!

🔄 **الأتمتة:**
🔔 تذكيرات فورية
🌐 مراقبة مواقع كل 5 دقائق
📊 تقرير يومي الساعة 8 صباحاً
📋 تذكير مهام الساعة 9 صباحاً

💬 أو كلمني عادي وأفهم! 🚀""")


# ═══════════════════════════════════════
# الصور
# ═══════════════════════════════════════
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 جاري تحليل الصورة...")
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        import tempfile
        image_path = os.path.join(tempfile.gettempdir(), f"img_{update.effective_user.id}.jpg")
        await file.download_to_drive(image_path)
        user_query = update.message.caption or ""
        result = await analyze_image(image_path, user_query)
        await update.message.reply_text(result)
        os.remove(image_path)
    except Exception as e:
        await update.message.reply_text(f"⚠️ خطأ: {str(e)}")


# ═══════════════════════════════════════
# البحث
# ═══════════════════════════════════════
async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else None
    if not query:
        await update.message.reply_text("🔍 /search كيف أتعلم Python")
        return
    await update.message.reply_text("🔍 جاري البحث...")
    result = await search_and_format(query)
    await update.message.reply_text(result)


# ═══════════════════════════════════════
# تنفيذ الأكواد
# ═══════════════════════════════════════
async def code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = " ".join(context.args) if context.args else None
    if not code:
        await update.message.reply_text("💻 /code print('Hello!')")
        return
    await update.message.reply_text("⚙️ جاري التنفيذ...")
    result = await execute_python_code(code)
    formatted = await format_code_result(result)
    await update.message.reply_text(formatted)


# ═══════════════════════════════════════
# المصاريف
# ═══════════════════════════════════════
async def spent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("💰 /spent 50 طعام قهوة")
        return
    try:
        amount = float(args[0])
        category = args[1] if len(args) > 1 else "أخرى"
        desc = " ".join(args[2:]) if len(args) > 2 else ""
        await add_expense(user_id, amount, category, desc)
        await update.message.reply_text(f"💰 تم تسجيل: {amount} ريال\n📁 {category}")
    except ValueError:
        await update.message.reply_text("⚠️ اكتب المبلغ كرقم")


async def expenses_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = await get_expenses_summary(user_id)
    report = f"""💰 مصاريفك الشهرية:
📊 الإجمالي: {data['total']:.2f} ريال

📁 حسب الفئة:
"""
    for cat in data['categories']:
        pct = (cat[1] / data['total'] * 100) if data['total'] > 0 else 0
        report += f"  {cat[0]}: {cat[1]:.2f} ({pct:.0f}%)\n"
    report += "\n📋 آخر المصاريف:\n"
    for exp in data['recent']:
        report += f"  💸 {exp[0]:.2f} - {exp[1]} - {exp[2]}\n"
    await update.message.reply_text(report)


# ═══════════════════════════════════════
# الإيميل
# ═══════════════════════════════════════
async def setemail_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "📧 /setemail your@gmail.com app_password\n\n"
            "💡 App Password:\n"
            "1. myaccount.google.com\n"
            "2. Security > 2FA > App Passwords\n"
            "3. أنشئ كلمة مرور")
        return
    email_service.configure(args[0], args[1])
    user_id = update.effective_user.id
    await update_profile(user_id, email=args[0])
    await update.message.reply_text(f"✅ تم إعداد: {args[0]}")


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    report = await generate_daily_report(user_id, user_name)
    await update.message.reply_text(report)
    if email_service.is_configured():
        profile = await get_profile(user_id)
        if profile and profile.get('email'):
            ok, msg = email_service.send_report(profile['email'], f"تقرير - {user_name}", report)
            await update.message.reply_text(msg)


# ═══════════════════════════════════════
# المواقع
# ═══════════════════════════════════════
async def addsite_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("🌐 /addsite https://example.com اسم")
        return
    url = args[0]
    name = " ".join(args[1:]) if len(args) > 1 else url
    await add_site(user_id, url, name)
    await update.message.reply_text(f"🌐 تمت إضافة: {name}\n🔗 {url}")


async def checksite_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = context.args[0] if context.args else None
    if not url:
        await update.message.reply_text("🌐 /checksite https://example.com")
        return
    await update.message.reply_text("🔍 جاري الفحص...")
    result = await check_site(url)
    await update.message.reply_text(f"🌐 {url}\n{result['message']}")


async def deepcheck_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = context.args[0] if context.args else None
    if not url:
        await update.message.reply_text("🔍 /deepcheck https://example.com")
        return
    await update.message.reply_text("🔍 جاري الفحص العميق...")
    report = await deep_check_site(url)
    text = await format_site_report(report)
    await update.message.reply_text(text)


# ═══════════════════════════════════════
# البناء الذاتي
# ═══════════════════════════════════════
async def build_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "🔧 /build اسم_الميزة وصف_الميزة\n\n"
            "مثال:\n"
            "/build أذكار أذكار الصباح والمساء")
        return
    name = context.args[0]
    desc = " ".join(context.args[1:]) if len(context.args) > 1 else name
    await update.message.reply_text(f"🔨 جاري بناء: {name}...\n⏳ أكتب الكود وأختبره...")
    success, log = await build_feature(user_id, name, desc)
    log_text = "\n".join(log)
    if success:
        await update.message.reply_text(f"🎉 تم بناء {name}!\n\n{log_text}\n\n▶️ /run {name}")
    else:
        await update.message.reply_text(f"❌ فشل:\n{log_text}")


async def run_feature_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("⚡ /run اسم_الميزة بيانات")
        return
    name = context.args[0]
    input_data = " ".join(context.args[1:]) if len(context.args) > 1 else ""
    await update.message.reply_text(f"⚙️ جاري تشغيل: {name}...")
    success, output = await execute_feature(user_id, name, input_data)
    if success:
        await update.message.reply_text(f"✅ نتيجة {name}:\n\n{output}")
    elif output == "الميزة غير موجودة":
        await update.message.reply_text(f"❌ '{name}' غير موجودة!\n💡 /build {name} وصف")
    else:
        await update.message.reply_text(f"❌ خطأ:\n{output}")


async def features_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    features = await get_all_features(user_id)
    if not features:
        await update.message.reply_text("🔧 ما عندك ميزات مبنية!\n\n💡 /build اسم وصف")
        return
    msg = "🔧 **الميزات المبنية:**\n\n"
    for f in features:
        msg += f"⚡ **{f[1]}**\n📝 {f[2]}\n📊 استخدام: {f[4]}\n▶️ /run {f[1]}\n\n"
    await update.message.reply_text(msg)


# ═══════════════════════════════════════
# الأدوات
# ═══════════════════════════════════════
async def password_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    length = int(context.args[0]) if context.args else 16
    password, strength = generate_password(length)
    await update.message.reply_text(
        f"🔐 كلمة مرور:\n\n`{password}`\n\n💪 {strength}\n📏 {length}",
        parse_mode='Markdown')


async def qr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args) if context.args else None
    if not text:
        await update.message.reply_text("📱 /qr https://example.com")
        return
    filename = generate_qr(text)
    if filename and os.path.exists(filename):
        await update.message.reply_photo(photo=open(filename, 'rb'))
        os.remove(filename)
    else:
        await update.message.reply_text("⚠️ خطأ توليد QR")


async def shorturl_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = context.args[0] if context.args else None
    if not url:
        await update.message.reply_text("🔗 /shorturl https://example.com")
        return
    result = await shorten_url(url)
    if result['success']:
        await update.message.reply_text(f"🔗 {result['short']}")
    else:
        await update.message.reply_text(f"⚠️ {result['error']}")


# ═══════════════════════════════════════
# الأوامر الأساسية
# ═══════════════════════════════════════
async def skills_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    skills = await get_skills(user_id)
    msg = """🧠 **المهارات المدمجة:**
  ✅ 🔍 بحث الإنترنت
  ✅ 💻 تنفيذ الأكواد
  ✅ 🖼️ تحليل الصور
  ✅ 📧 إرسال إيميلات
  ✅ 💰 تتبع المصاريف
  ✅ 🔐 كلمات مرور
  ✅ 📱 QR Code
  ✅ 🔗 تقصير روابط
  ✅ 🌐 فحص المواقع
  ✅ 📊 تقارير
  ✅ 🔧 بناء ذاتي
"""
    if skills:
        msg += "\n🧠 **مهارات مُتعلمة:**\n"
        for s in skills:
            msg += f"  ✅ {s[0]}: {s[1]}\n"
    await update.message.reply_text(msg)


async def addtask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = " ".join(context.args) if context.args else None
    if not text:
        await update.message.reply_text("📝 /addtask تعلم Python")
        return
    await add_task(user_id, text)
    await update.message.reply_text(f"✅ تمت إضافة: {text}")


async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tasks = await get_tasks(user_id)
    if not tasks:
        await update.message.reply_text("🎉 ما عندك مهام معلقة!")
        return
    msg = "📋 **مهامك:**\n\n"
    for t in tasks:
        p = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(t[2], "🟡")
        msg += f"{p} [{t[0]}] {t[1]}\n"
    msg += "\n✅ إنهاء: /donetask رقم"
    await update.message.reply_text(msg)


async def donetask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("✅ /donetask رقم")
        return
    try:
        await complete_task(user_id, int(context.args[0]))
        await update.message.reply_text(f"🎉 أحسنت! #{context.args[0]}")
    except:
        await update.message.reply_text("⚠️ رقم غير صحيح")


async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = " ".join(context.args) if context.args else None
    if not text:
        await update.message.reply_text("📝 /note نص الملاحظة")
        return
    await save_note(user_id, "ملاحظة", text)
    await update.message.reply_text(f"💾 تم الحفظ")


async def mynotes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    notes = await get_notes(user_id)
    if not notes:
        await update.message.reply_text("📭 ما عندك ملاحظات")
        return
    msg = "📚 **ملاحظاتك:**\n\n"
    for n in notes:
        msg += f"📌 {n[2][:100]}\n\n"
    await update.message.reply_text(msg)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stats = await get_full_stats(user_id)
    await update.message.reply_text(f"""📊 **إحصائياتك:**

💬 رسائل: {stats['messages']}
📋 مهام معلقة: {stats['pending_tasks']}
✅ مهام منجزة: {stats['done_tasks']}
🧠 مهارات: {stats['skills']}
📝 ملاحظات: {stats['notes']}
🔔 تذكيرات: {stats['active_reminders']}
🌐 مواقع: {stats['monitored_sites']}
💾 ذكريات: {stats['memories']}""")


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    profile = await get_profile(user_id)
    if profile:
        await update.message.reply_text(f"""📋 **ملفك:**
👤 {profile.get('name', '?')}
📧 {profile.get('email', 'غير محدد')}
🎯 {profile.get('goals', 'لم يحدد')}""")
    else:
        await update.message.reply_text("📋 كلمني وأبني ملفك!")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    import aiosqlite
    from config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM conversations WHERE user_id=?", (user_id,))
        await db.commit()
    await update.message.reply_text("🗑️ تم مسح المحادثات!")


# ═══════════════════════════════════════
# معالجة الرسائل
# ═══════════════════════════════════════
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    user_message = update.message.text

    await set_owner(user_id, user_name)
    await save_message(user_id, user_name, "user", user_message)
    await update_profile(user_id, name=user_name)

    raw_reply = await get_smart_reply(user_id, user_name, user_message)
    clean_reply, actions = await parse_and_execute(user_id, raw_reply)

    if actions:
        clean_reply += "\n\n" + "\n".join(actions)

    await save_message(user_id, user_name, "assistant", clean_reply)
    await update.message.reply_text(clean_reply)

    print(f"✅ [{user_name}]: {user_message[:50]}")
    print(f"🤖 [{AGENT_NAME}]: {clean_reply[:50]}\n")


# ═══════════════════════════════════════
# التشغيل
# ═══════════════════════════════════════
def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_database())
    loop.run_until_complete(init_self_builder())

    print("=" * 60)
    print(f"🚀 {AGENT_NAME} v5.0 - على السيرفر!")
    print("📱 البوت شغّال 24/7!")
    print("=" * 60)

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # تشغيل المهام الخلفية
    async def post_init(application):
        asyncio.create_task(background_scheduler(application.bot))
        print("🔄 الأتمتة مفعّلة!")

    app.post_init = post_init

    # أوامر النظام
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("skills", skills_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("clear", clear_command))

    # الإنتاجية
    app.add_handler(CommandHandler("addtask", addtask_command))
    app.add_handler(CommandHandler("tasks", tasks_command))
    app.add_handler(CommandHandler("donetask", donetask_command))
    app.add_handler(CommandHandler("note", note_command))
    app.add_handler(CommandHandler("mynotes", mynotes_command))

    # الذكاء
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("code", code_command))

    # المالية
    app.add_handler(CommandHandler("spent", spent_command))
    app.add_handler(CommandHandler("expenses", expenses_command))

    # المراقبة
    app.add_handler(CommandHandler("addsite", addsite_command))
    app.add_handler(CommandHandler("checksite", checksite_command))
    app.add_handler(CommandHandler("deepcheck", deepcheck_command))

    # التقارير
    app.add_handler(CommandHandler("setemail", setemail_command))
    app.add_handler(CommandHandler("report", report_command))

    # الأدوات
    app.add_handler(CommandHandler("password", password_command))
    app.add_handler(CommandHandler("qr", qr_command))
    app.add_handler(CommandHandler("shorturl", shorturl_command))

    # البناء الذاتي
    app.add_handler(CommandHandler("build", build_command))
    app.add_handler(CommandHandler("run", run_feature_command))
    app.add_handler(CommandHandler("features", features_command))

    # الصور
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # الرسائل
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("\n⏳ في انتظار الرسائل...\n")
    app.run_polling()


if __name__ == "__main__":
    main()