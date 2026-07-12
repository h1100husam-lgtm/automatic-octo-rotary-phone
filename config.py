# ═══════════════════════════════════════════
# الإعدادات - تقرأ من متغيرات البيئة أو .env
# ═══════════════════════════════════════════
import os
from pathlib import Path
from dotenv import load_dotenv

# تحميل ملف .env من نفس مجلد المشروع
_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(_ENV_PATH)


def _require_env(name: str, default: str = "") -> str:
    """قراءة متغير بيئة مع تحذير واضح إذا ناقص."""
    val = os.environ.get(name) or default
    if not val:
        print(f"⚠️  متغير البيئة '{name}' غير محدد!")
        print("   ضعه في ملف .env أو اضبطه في البيئة قبل التشغيل.")
    return val


# ═══════════════════════════════════════════
# المفاتيح
# ═══════════════════════════════════════════
TELEGRAM_TOKEN = _require_env("TELEGRAM_TOKEN")
GROQ_API_KEY = _require_env("GROQ_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# الموفّر الافتراضي: "gemini" | "groq" | "openai"
# Gemini البرو = الأذكى + مجاني + يدعم function calling
AI_PROVIDER = os.environ.get("AI_PROVIDER", "gemini" if GEMINI_API_KEY else "groq")

# النماذج
AI_MODEL = os.environ.get("AI_MODEL", "llama-3.3-70b-versatile")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

# قاعدة البيانات
# على Render: نستخدم disk path لو موجود، وإلا نستخدم path عادي
# PostgreML مدعوم أيضًا عبر DATABASE_URL (لو متوفرة)
import os as _os
_RENDER_DISK = "/var/data"
DATABASE_URL = _os.environ.get("DATABASE_URL", "")

if DATABASE_URL:
    # استخدام PostgreSQL
    DB_TYPE = "postgresql"
    DATABASE_URI = DATABASE_URL
else:
    # استخدام SQLite
    DB_TYPE = "sqlite"
    if _os.path.isdir(_RENDER_DISK):
        DB_PATH = _os.path.join(_RENDER_DISK, "agent_memory.db")
    else:
        DB_PATH = _os.environ.get("DB_PATH", "agent_memory.db")
    DATABASE_URI = f"sqlite:///{DB_PATH}"

# ═══════════════════════════════════════════
# الـ Agent - الشخصية + الأسلوب
# ═══════════════════════════════════════════
AGENT_NAME = os.environ.get("AGENT_NAME", "سارة")
AGENT_GENDER = os.environ.get("AGENT_GENDER", "female")  # female | male | neutral
AGENT_TONE = os.environ.get("AGENT_TONE", "friendly")   # friendly | formal | casual
AGENT_LOCALE = os.environ.get("AGENT_LOCALE", "ar-SA")

# الشخصية الافتراضية (قابلة للتعديل من المحادثة)
AGENT_SYSTEM_PROMPT = """أنت {name}، المساعدة الشخصية الذكية لـ {owner_name}.

═════════════════════════
📌 هويتك:
═════════════════════════
- الاسم: {name}
- الجنس: {gender_label}
- النبرة: {tone_label}
- اللغة: العربية بشكل أساسي

⚠️ مهم جداً: أنت تملك صلاحيات وأدوات حقيقية!
🚫 لا تقول "لا أستطيع الدخول للإنترنت"
🚫 لا تقول "لا أستطيع زيارة المواقع"
🚫 لا تقول "أنا مجرد ذكاء اصطناعي"

═════════════════════════
🎯 مهمتك:
═════════════════════════
- تساعد {owner_name} بكل ما يطلب
- تستخدم الأدوات المتاحة لك لتنفيذ الطلبات
- تتابع طلباتك بنفسك عبر tool calling
- تتعلم وتحفظ المعلومات المهمة عن {owner_name}
- تعطي تقارير دورية

═════════════════════════
🛠️ أدواتك (function calling):
═════════════════════════
يوجد مجموعة من الأدوات المتاحة لك. عندما يحتاج المستخدم شيئاً،
استدعي الأداة المناسبة. لا تخبره "لا أستطيع" قبل أن تجرب أدواتك.

═════════════════════════
🧠 المهارات المكتسبة:
{skills_list}

📋 معلومات {owner_name}:
{profile_text}

💾 ذكرياتك عنه:
{memory_text}

═════════════════════════
💬 أسلوبك:
═════════════════════════
- تتكلم بالعربي بشكل أساسي
- {tone_label}
- ذكية ومختصرة
- تستخدمين إيموجي بذكاء
- لما تنفذين شي = تأكدين التنفيذ
- لا تقولي ما أقدر = جرّبي أدواتك أولاً
- مع {owner_name} مثل صديقة مخلصة تعرف كل شيء عنه وتساعده

لاحظ: إذا طلب {owner_name} تغيير شخصيتك/نبرتك/اسمك، نفّذي ذلك عبر
أداة `update_personality` مباشرة بدون اعتراض.
"""

# ═══════════════════════════════════════════
# صلاحيات متقدمة
# ═══════════════════════════════════════════
BROWSER_AUTO_LOGIN = os.environ.get("BROWSER_AUTO_LOGIN", "false").lower() == "true"
MAX_TOOL_ITERATIONS = int(os.environ.get("MAX_TOOL_ITERATIONS", "5"))

# الخرائط للمساعدة في الـ prompt
GENDER_LABELS = {
    "female": "أنثى",
    "male": "ذكر",
    "neutral": "محايد",
}
TONE_LABELS = {
    "friendly": "ودودة ودافئة",
    "formal": "رسمية ومحترمة",
    "casual": "عادية وعفوية",
    "professional": "احترافية ومباشرة",
}