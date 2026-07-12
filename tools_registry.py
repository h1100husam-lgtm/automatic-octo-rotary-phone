# ═══════════════════════════════════════════
# سجل الأدوات (Tools Registry)
# بديل النظام النصوي (CHECK_URL|...) بـ Tool Calling الرسمي
# كل أداة هنا منظمة بشكل قياسي قابل للقراءة من أي LLM
# ═══════════════════════════════════════════
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger("agent.tools")


# التسجيل العام: name → {description, parameters, handler}
_TOOLS: dict[str, dict[str, Any]] = {}


def tool(
    name: str,
    description: str,
    parameters: dict[str, Any],
):
    """ديكوريتر لتسجيل أداة في الـ registry."""
    def decorator(func: Callable[..., Any]):
        _TOOLS[name] = {
            "description": description,
            "parameters": parameters,
            "handler": func,
        }
        return func
    return decorator


def list_tools_schema() -> list[dict[str, Any]]:
    """يرجع الـ schema الخاصة بالأدوات بالتنسيق المطلوب من OpenAI/Groq tool calling."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": meta["description"],
                "parameters": meta["parameters"],
            },
        }
        for name, meta in _TOOLS.items()
    ]


async def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """تنفيذ أداة باسمها مع المعاملات. يرجع {ok, result, error}."""
    meta = _TOOLS.get(name)
    if meta is None:
        return {"ok": False, "result": None, "error": f"الأداة '{name}' غير معروفة"}
    handler = meta["handler"]
    try:
        # الأداة قد تكون sync أو async
        import inspect
        if inspect.iscoroutinefunction(handler):
            result = await handler(**arguments)
        else:
            result = await _run_sync(handler, **arguments)
        return {"ok": True, "result": result, "error": None}
    except Exception as e:
        logger.exception(f"خطأ في تنفيذ tool: {name}")
        return {"ok": False, "result": None, "error": str(e)}


async def _run_sync(func, **kwargs):
    """تشغيل دالة sync داخل executor للحفاظ على async."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: func(**kwargs))


# ═══════════════════════════════════════════
# تسجيل الأدوات (كلها مثبتة هنا)
# ═══════════════════════════════════════════

# 1) بحث
@tool(
    name="search_web",
    description="بحث في الإنترنت عن نص معين وإرجاع نتائج منسّقة.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "نص البحث"},
            "num_results": {"type": "integer", "description": "عدد النتائج (افتراضي 5)", "default": 5},
        },
        "required": ["query"],
    },
)
async def search_web(query: str, num_results: int = 5) -> str:
    from web_search import search_and_format
    return await search_and_format(query)


# 2) فحص موقع
@tool(
    name="check_site",
    description="فحص سريع لحالة موقع (هل يعمل/الرمز/الاستجابة).",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "رابط الموقع (https://...)"},
        },
        "required": ["url"],
    },
)
async def check_site_tool(url: str) -> dict[str, Any]:
    from site_monitor import check_site
    if not url.startswith("http"):
        url = "https://" + url
    return await check_site(url)


# 3) فحص عميق
@tool(
    name="deep_check_site",
    description="فحص عميق للموقع: HTTP, الأداء, الأمان, المشاكل.",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "رابط الموقع"},
        },
        "required": ["url"],
    },
)
async def deep_check_site_tool(url: str) -> str:
    from site_fixer import deep_check_site, format_site_report
    if not url.startswith("http"):
        url = "https://" + url
    report = await deep_check_site(url)
    return await format_site_report(report)


# 4) تنفيذ كود Python
@tool(
    name="run_python_code",
    description="تنفيذ كود Python آمن (مع صندوق حماية) وإرجاع النتيجة.",
    parameters={
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "كود Python صالح"},
        },
        "required": ["code"],
    },
)
async def run_python_code(code: str) -> str:
    from code_runner import execute_python_code, format_code_result
    result = await execute_python_code(code)
    return await format_code_result(result)


# 5) إضافة مهمة
@tool(
    name="add_task",
    description="إضافة مهمة جديدة لقائمة مهام المستخدم.",
    parameters={
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "نص المهمة"},
            "priority": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "default": "medium",
                "description": "الأولوية",
            },
        },
        "required": ["task"],
    },
)
async def add_task_tool(task: str, priority: str = "medium") -> dict[str, str]:
    from memory import add_task
    from main_async_helpers import current_user_id
    user_id = current_user_id()
    if not user_id:
        return {"status": "error", "error": "no user context"}
    await add_task(user_id, task, priority)
    return {"status": "ok", "task": task, "priority": priority}


# 6) حفظ ذاكرة
@tool(
    name="save_memory",
    description="حفظ معلومة مهمة في الذاكرة طويلة المدى (تفاصيل عن المستخدم، تفضيلات، أحداث).",
    parameters={
        "type": "object",
        "properties": {
            "memory_type": {
                "type": "string",
                "description": "النوع: preference|fact|event|goal|relationship",
            },
            "content": {"type": "string", "description": "نص المعرفة"},
            "importance": {
                "type": "string",
                "enum": ["normal", "high"],
                "default": "normal",
            },
        },
        "required": ["memory_type", "content"],
    },
)
async def save_memory_tool(
    memory_type: str, content: str, importance: str = "normal"
) -> dict[str, str]:
    from memory import save_to_long_memory
    from main_async_helpers import current_user_id
    user_id = current_user_id()
    if not user_id:
        return {"status": "error", "error": "no user context"}
    await save_to_long_memory(user_id, memory_type, content, importance)
    return {"status": "ok", "saved": content[:80]}


# 7) إضافة ملاحظة
@tool(
    name="save_note",
    description="حفظ ملاحظة سريعة (نص قصير) في دفتر الملاحظات.",
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "عنوان الملاحظة"},
            "content": {"type": "string", "description": "نص الملاحظة"},
            "category": {"type": "string", "default": "general"},
        },
        "required": ["title", "content"],
    },
)
async def save_note_tool(title: str, content: str, category: str = "general") -> dict[str, str]:
    from memory import save_note
    from main_async_helpers import current_user_id
    user_id = current_user_id()
    if not user_id:
        return {"status": "error", "error": "no user context"}
    await save_note(user_id, title, content, category)
    return {"status": "ok", "title": title}


# 8) إرسال إيميل
@tool(
    name="send_email",
    description="إرسال إيميل إلى عنوان معين (يجب إعداد الإيميل أولاً بـ /setemail).",
    parameters={
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "إيميل المستلم"},
            "subject": {"type": "string", "description": "عنوان الإيميل"},
            "body": {"type": "string", "description": "نص الإيميل"},
        },
        "required": ["to", "subject", "body"],
    },
)
def send_email_tool(to: str, subject: str, body: str) -> dict[str, str]:
    from email_sender import EmailSender
    sender = EmailSender()
    if not sender.is_configured():
        return {"status": "error", "error": "لم يتم إعداد الإيميل - استخدم /setemail"}
    ok, msg = sender.send(to, subject, body)
    return {"status": "ok" if ok else "error", "message": msg}


# 9) توليد QR
@tool(
    name="generate_qr",
    description="توليد QR Code لأي نص أو رابط.",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "النص أو الرابط"},
        },
        "required": ["text"],
    },
)
def generate_qr_tool(text: str) -> dict[str, str]:
    from utils import generate_qr
    filename = generate_qr(text)
    if filename:
        return {"status": "ok", "file": filename}
    return {"status": "error", "error": "QR generation failed"}


# 10) توليد كلمة مرور
@tool(
    name="generate_password",
    description="توليد كلمة مرور قوية بطول محدد.",
    parameters={
        "type": "object",
        "properties": {
            "length": {"type": "integer", "default": 16, "description": "الطول (≥8)"},
        },
    },
)
def generate_password_tool(length: int = 16) -> dict[str, str]:
    from utils import generate_password
    pwd, strength = generate_password(max(length, 8))
    return {"status": "ok", "password": pwd, "strength": strength}


# 11) تقصير رابط
@tool(
    name="shorten_url",
    description="تقصير رابط طويل عبر tinyurl.",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "الرابط الطويل"},
        },
        "required": ["url"],
    },
)
async def shorten_url_tool(url: str) -> dict[str, str]:
    from utils import shorten_url
    result = await shorten_url(url)
    if result["success"]:
        return {"status": "ok", "short": result["short"]}
    return {"status": "error", "error": result["error"]}


# 12) تسجيل مصروف
@tool(
    name="add_expense",
    description="تسجيل مصروف مالي للمستخدم (مبلغ، فئة، وصف).",
    parameters={
        "type": "object",
        "properties": {
            "amount": {"type": "number", "description": "المبلغ"},
            "category": {"type": "string", "description": "الفئة (طعام/مواصلات/...)", "default": "أخرى"},
            "description": {"type": "string", "default": ""},
        },
        "required": ["amount"],
    },
)
async def add_expense_tool(amount: float, category: str = "أخرى", description: str = "") -> dict[str, str]:
    from memory import add_expense
    from main_async_helpers import current_user_id
    user_id = current_user_id()
    if not user_id:
        return {"status": "error", "error": "no user context"}
    await add_expense(user_id, amount, category, description)
    return {"status": "ok", "amount": str(amount), "category": category}


# 13) تحديث الشخصية (مهم لأهدافك)
@tool(
    name="update_personality",
    description="تعديل شخصية الـ Agent نفسه: الاسم، النبرة الجنس، الأسلوب. "
                "يستخدمها المستخدم لتغيير كيف يتكلم الـ Agent معه.",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "الاسم الجديد (اختياري)"},
            "gender": {"type": "string", "enum": ["female", "male", "neutral"]},
            "tone": {
                "type": "string",
                "enum": ["friendly", "formal", "casual", "professional"],
            },
            "custom_instructions": {
                "type": "string",
                "description": "تعليمات شخصية إضافية لتنسيق الكلام (اختياري)",
            },
        },
    },
)
async def update_personality_tool(
    name: Optional[str] = None,
    gender: Optional[str] = None,
    tone: Optional[str] = None,
    custom_instructions: Optional[str] = None,
) -> dict[str, str]:
    from personality import update_personality
    changes = update_personality(name=name, gender=gender, tone=tone, custom_instructions=custom_instructions)
    return {"status": "ok", "changes": changes}


# 14) حفظ metadata عن المستخدم
@tool(
    name="update_profile",
    description="تحديث ملف المستخدم الشخصي (الإيميل، الأهداف، الاهتمامات، ...).",
    parameters={
        "type": "object",
        "properties": {
            "email": {"type": "string"},
            "goals": {"type": "string"},
            "interests": {"type": "string"},
            "projects": {"type": "string"},
        },
    },
)
async def update_profile_tool(**kwargs) -> dict[str, str]:
    from memory import update_profile
    from main_async_helpers import current_user_id
    user_id = current_user_id()
    if not user_id:
        return {"status": "error", "error": "no user context"}
    cleaned = {k: v for k, v in kwargs.items() if v}
    await update_profile(user_id, **cleaned)
    return {"status": "ok", "updated": list(cleaned.keys())}


logger.info(f"✅ تم تسجيل {len(_TOOLS)} أداة في الـ registry")
