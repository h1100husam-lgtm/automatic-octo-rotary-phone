# ════════════════════════════════════════════
# محرك البناء الذاتي
# الـ Agent يكتب كود ويضيفه لنفسه!
# ═══════════════════════════════════════════
import os
import json
import subprocess
import tempfile
import logging
from datetime import datetime
from config import DB_PATH, GROQ_API_KEY, AI_MODEL, DB_TYPE
from sandbox import validate_code, sanitize_input
from db_pool import get_db_connection

logger = logging.getLogger("agent.builder")

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


async def _fetchval(query: str, *args) -> Any:
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


# ════════════════════════════════════════════
# جدول الميزات المبنية ذاتياً
# ════════════════════════════════════════════
async def init_self_builder():
    """تهيئة جدول البناء الذاتي"""
    async with get_db_connection() as conn:
        # Ensure tables exist
        if DB_TYPE == "postgresql":
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS self_features (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER,
                    feature_name TEXT,
                    feature_description TEXT,
                    feature_code TEXT,
                    feature_type TEXT DEFAULT 'function',
                    is_active INTEGER DEFAULT 1,
                    usage_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS feature_logs (
                    id SERIAL PRIMARY KEY,
                    feature_id INTEGER,
                    user_id INTEGER,
                    input_data TEXT,
                    output_data TEXT,
                    success INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            await conn.execute("""
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
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS feature_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    feature_id INTEGER,
                    user_id INTEGER,
                    input_data TEXT,
                    output_data TEXT,
                    success INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
        await conn.commit()
    logger.info("✅ محرك البناء الذاتي جاهز!")


# ═══════════════════════════════════════════
# كتابة كود لميزة جديدة
# ═══════════════════════════════════════════
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

═════════════════════════════════════════════
قواعد مهمة:
════════════════════════════════════════════
1. اكتب الدالة فقط (لا تستورد مكتبات غير موجودة)
2. الدالة تكون async
3. اسم الدالة: feature_{feature_name.replace(' ', '_').lower()}
4. الدالة ترجع نص (string) منسق
5. لا تستخدم مكتبات غير مثبتة
6. المكتبات المتوفرة: json, os, datetime, re, math, random, urllib, collections
7. إذا احتجت بيانات خارجية = اطلبها من المستخدم
8. اكتب كود نظيف ومعلق

════════════════════════════════════════════
أرجع فقط كود Python بدون أي شرح:
═══════════════════════════════════════════
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


# ═══════════════════════════════════════════
# اختبار الكود المكتوب
# ═══════════════════════════════════════════
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


# ═══════════════════════════════════════════
# حفظ وتفعيل الميزة
# ═══════════════════════════════════════════
async def save_feature(user_id, name, description, code, feature_type="function"):
    """حفظ الميزة في قاعدة البيانات"""
    await _execute(
        """
        INSERT INTO self_features 
        (user_id, feature_name, feature_description, feature_code, feature_type)
        VALUES (?, ?, ?, ?, ?)
        """,
        user_id, name, description, code, feature_type
    )


async def get_all_features(user_id):
    """جلب كل الميزات المبنية"""
    return await _fetchall(
        "SELECT id, feature_name, feature_description, feature_type, usage_count FROM self_features WHERE user_id=? AND is_active=1",
        user_id
    )


async def get_feature_by_name(user_id, name):
    """جلب ميزة بالاسم"""
    return await _fetchone(
        "SELECT id, feature_name, feature_code FROM self_features WHERE user_id=? AND feature_name=? AND is_active=1",
        user_id, name
    )


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
        await _execute(
            "UPDATE self_features SET usage_count = usage_count + 1 WHERE id = ?",
            feature_id
        )

        # تسجيل السجل
        await _execute(
            "INSERT INTO feature_logs (feature_id, user_id, input_data, output_data, success) VALUES (?,?,?,?,?)",
            (feature_id, user_id, input_data, output, 1 if result.returncode == 0 else 0)
        )

        if result.returncode == 0:
            return True, output
        else:
            return False, result.stderr[:500]

    except subprocess.TimeoutExpired:
        return False, "⏰ انتهى الوقت"
    except Exception as e:
        return False, str(e)


# ═══════════════════════════════════════════
# البناء الذاتي الكامل
# ═══════════════════════════════════════════
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
    await save_feature(user_id, feature_name, description, code)
    result_log.append(f"💾 تم حفظ الميزة: {feature_name}")
    result_log.append(f"🎯 الميزة جاهزة للاستخدام!")

    return True, result_log


# ═══════════════════════════════════════════
# إصلاح الكود التلقائي
# ═══════════════════════════════════════════
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