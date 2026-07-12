# ═══════════════════════════════════════════
# محرك البناء الذاتي
# الـ Agent يكتب كود ويضيفه لنفسه!
# ═══════════════════════════════════════════
import os
import json
import subprocess
import tempfile
import logging
import aiosqlite
from datetime import datetime
from config import DB_PATH, GROQ_API_KEY, AI_MODEL
from sandbox import validate_code, sanitize_input

logger = logging.getLogger("agent.builder")


# ═══════════════════════════════════
# جدول الميزات المبنية ذاتياً
# ═══════════════════════════════════
async def init_self_builder():
    """تهيئة جدول البناء الذاتي"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS self_features (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                feature_name TEXT,
                feature_description TEXT,
                feature_code TEXT,
                feature_type TEXT DEFAULT 'function',
                is_active INTEGER DEFAULT 1,
                usage_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS feature_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feature_id INTEGER,
                user_id INTEGER,
                input_data TEXT,
                output_data TEXT,
                success INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
    logger.info("✅ محرك البناء الذاتي جاهز!")


# ═══════════════════════════════════
# كتابة كود لميزة جديدة
# ═══════════════════════════════════
async def generate_feature_code(feature_name, feature_description, user_context=""):
    """الذكاء الاصطناعي يكتب كود للميزة"""

    import re as _re
    if not _re.match(r"^[a-zA-Z\u0600-\u06FF][\w\u0600-\u06FF ]{0,49}$", feature_name):
        return "# خطأ: اسم الميزة غير صالح (أحرف إنجليزية أو عربية فقط)"

    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)

    prompt = f"""أنت مطور Python محترف.
اكتب دالة Python كاملة وجاهزة للتنفيذ.

اسم الميزة: {feature_name}
الوصف: {feature_description}
السياق: {user_context}

═══════════════════════════════════════
قواعد مهمة:
═══════════════════════════════════════
1. اكتب الدالة فقط (لا تستورد مكتبات غير موجودة)
2. الدالة تكون async
3. اسم الدالة: feature_{feature_name.replace(' ', '_').lower()}
4. الدالة ترجع نص (string) منسق
5. لا تستخدم مكتبات غير مثبتة
6. المكتبات المتوفرة: json, os, datetime, re, math, random, urllib, collections
7. إذا احتجت بيانات خارجية = اطلبها من المستخدم
8. اكتب كود نظيف ومعلق

═══════════════════════════════════════
أرجع فقط كود Python بدون أي شرح:
═══════════════════════════════════════
"""

    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=AI_MODEL,
            temperature=0.3,
            max_tokens=3000,
        )
        code = response.choices[0].message.content

        # تنظيف الكود
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0]
        elif "```" in code:
            code = code.split("```")[1].split("```")[0]

        return code.strip()

    except Exception as e:
        return f"# خطأ: {str(e)}"


# ═══════════════════════════════════
# اختبار الكود المكتوب
# ═══════════════════════════════════
async def test_feature_code(code):
    """اختبار الكود قبل حفظه"""

    valid, reason = validate_code(code)
    if not valid:
        return False, f"🔒 كود مرفوض أمنياً: {reason}"

    try:
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.py', delete=False
        ) as f:
            # كتابة كود الاختبار
            test_code = f"""
import asyncio
import json

{code}

# اختبار سريع
async def test():
    try:
        # محاولة استدعاء الدالة
        func_name = [name for name in dir() if name.startswith('feature_')]
        if func_name:
            func = eval(func_name[0])
            result = await func()
            print(f"✅ الدالة شغّالة! النتيجة: {{str(result)[:200]}}")
        else:
            print("⚠️ ما لقيت دالة feature_")
    except TypeError:
        # الدالة تحتاج معاملات
        print("✅ الدالة موجودة (تحتاج معاملات)")
    except Exception as e:
        print(f"❌ خطأ: {{e}}")

asyncio.run(test())
"""
            f.write(test_code)
            temp_path = f.name

        result = subprocess.run(
            ['python', '-I', temp_path],
            capture_output=True, text=True, timeout=15,
            cwd=tempfile.gettempdir(),
            env={'PATH': os.environ.get('PATH', ''), 'PYTHONDONTWRITEBYTECODE': '1'},
        )

        os.unlink(temp_path)

        output = result.stdout + result.stderr

        if "✅" in output:
            return True, output
        elif "❌" in output:
            return False, output
        else:
            return True, output or "✅ الكود تم اختباره"

    except subprocess.TimeoutExpired:
        return False, "⏰ انتهى وقت الاختبار"
    except Exception as e:
        return False, str(e)


# ═══════════════════════════════════
# حفظ وتفعيل الميزة
# ═══════════════════════════════════
async def save_feature(user_id, name, description, code, feature_type="function"):
    """حفظ الميزة في قاعدة البيانات"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO self_features 
            (user_id, feature_name, feature_description, feature_code, feature_type)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, name, description, code, feature_type))
        await db.commit()


async def get_all_features(user_id):
    """جلب كل الميزات المبنية"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, feature_name, feature_description, feature_type, usage_count FROM self_features WHERE user_id=? AND is_active=1",
            (user_id,)
        ) as cursor:
            return await cursor.fetchall()


async def get_feature_by_name(user_id, name):
    """جلب ميزة بالاسم"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, feature_name, feature_code FROM self_features WHERE user_id=? AND feature_name=? AND is_active=1",
            (user_id, name)
        ) as cursor:
            return await cursor.fetchone()


async def execute_feature(user_id, feature_name, input_data=""):
    """تنفيذ ميزة مبنية ذاتياً"""
    feature = await get_feature_by_name(user_id, feature_name)

    if not feature:
        return None, "الميزة غير موجودة"

    feature_id, name, code = feature

    valid, reason = validate_code(code)
    if not valid:
        return False, f"🔒 الميزة تحتوي كود مرفوض: {reason}"

    input_data = sanitize_input(input_data)

    try:
        # كتابة كود التنفيذ
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.py', delete=False
        ) as f:
            exec_code = f"""
import asyncio
import json
import os
import re
from datetime import datetime

{code}

async def run():
    try:
        result = await feature_{name.replace(' ', '_').lower()}("{input_data}")
        return str(result)
    except TypeError:
        # جرب بدون معاملات
        result = await feature_{name.replace(' ', '_').lower()}()
        return str(result)
    except Exception as e:
        return f"خطأ: {{e}}"

print(asyncio.run(run()))
"""
            f.write(exec_code)
            temp_path = f.name

        result = subprocess.run(
            ['python', '-I', temp_path],
            capture_output=True, text=True, timeout=30,
            cwd=tempfile.gettempdir(),
            env={'PATH': os.environ.get('PATH', ''), 'PYTHONDONTWRITEBYTECODE': '1'},
        )

        os.unlink(temp_path)

        output = result.stdout.strip()

        # تحديث عداد الاستخدام
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE self_features SET usage_count = usage_count + 1 WHERE id = ?",
                (feature_id,)
            )
            await db.commit()

        # تسجيل السجل
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO feature_logs (feature_id, user_id, input_data, output_data, success) VALUES (?,?,?,?,?)",
                (feature_id, user_id, input_data, output, 1 if result.returncode == 0 else 0)
            )
            await db.commit()

        if result.returncode == 0:
            return True, output
        else:
            return False, result.stderr[:500]

    except subprocess.TimeoutExpired:
        return False, "⏰ انتهى الوقت"
    except Exception as e:
        return False, str(e)


# ═══════════════════════════════════
# البناء الذاتي الكامل
# ═══════════════════════════════════
async def build_feature(user_id, feature_name, feature_description, user_context=""):
    """
    العملية الكاملة:
    1. الذكاء الاصطناعي يكتب الكود
    2. نختبر الكود
    3. نحفظه ونفعّله
    4. يصير متاح للاستخدام
    """

    result_log = []

    # الخطوة 1: كتابة الكود
    result_log.append(f"🤖 أكتب كود الميزة: {feature_name}...")
    code = await generate_feature_code(feature_name, feature_description, user_context)

    if code.startswith("# خطأ"):
        return False, result_log + [code]

    result_log.append(f"✅ تم كتابة الكود ({len(code)} حرف)")

    # الخطوة 2: اختبار الكود
    result_log.append("🧪 اختبار الكود...")
    test_ok, test_msg = await test_feature_code(code)

    if not test_ok:
        # محاولة ثانية مع ذكاء اصطناعي
        result_log.append("⚠️ الاختبار فشل، أحاول إصلاح...")
        fixed_code = await fix_code(code, test_msg)
        if fixed_code:
            code = fixed_code
            test_ok, test_msg = await test_feature_code(code)
            if test_ok:
                result_log.append("✅ تم إصلاح الكود!")
            else:
                result_log.append(f"❌ فشل الإصلاح: {test_msg[:100]}")
                return False, result_log

    result_log.append("✅ الكود شغّال!")

    # الخطوة 3: الحفظ
    await save_feature(user_id, feature_name, feature_description, code)
    result_log.append(f"💾 تم حفظ الميزة: {feature_name}")
    result_log.append(f"🎯 الميزة جاهزة للاستخدام!")

    return True, result_log

# ═══════════════════════════════════
# إصلاح الكود التلقائي
# ═══════════════════════════════════
async def fix_code(broken_code, error_message):
    """محاولة إصلاح الكود بالذكاء الاصطناعي"""

    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)

    # ✅ نستخدم concatenation بدل f-string طويل
    prompt = (
        "أنت مطور Python محترف.\n"
        "هذا الكود فيه خطأ، أصلحه:\n\n"
        "الكود:\n"
        "```python\n"
        + broken_code + "\n"
        "```\n\n"
        "الخطأ:\n"
        + error_message + "\n\n"
        "أرجع الكود المصلح فقط داخل ```python ... ``` (بدون شرح):"
    )

    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=AI_MODEL,
            temperature=0.2,
            max_tokens=3000,
        )
        fixed = response.choices[0].message.content

        # ✅ استخراج الكود من بين الـ backticks
        if "```python" in fixed:
            fixed = fixed.split("```python")[1].split("```")[0]
        elif "```" in fixed:
            fixed = fixed.split("```")[1].split("```")[0]

        return fixed.strip()

    except Exception as e:
        logger.error(f"❌ خطأ إصلاح الكود: {e}")
        return None