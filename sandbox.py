# ═══════════════════════════════════════════
# صندوق الحماية - منع الكود الخطر قبل التنفيذ
# ═══════════════════════════════════════════
import re
from typing import Tuple

# كلمات/أنماط ممنوعة في الكود المُنفّذ من AI
_DANGEROUS_PATTERNS = [
    (r"\bos\.system\s*\(", "os.system"),
    (r"\bos\.popen\s*\(", "os.popen"),
    (r"\bsubprocess\.", "subprocess"),
    (r"\bPopen\b", "Popen"),
    (r"\bos\.exec", "os.exec"),
    (r"\bos\.remove\s*\(", "os.remove"),
    (r"\bos\.unlink\s*\(", "os.unlink"),
    (r"\bos\.rmdir\s*\(", "os.rmdir"),
    (r"\bshutil\.rmtree", "shutil.rmtree"),
    (r"\b__import__\s*\(", "__import__"),
    (r"\beval\s*\(", "eval"),
    (r"\bexec\s*\(", "exec"),
    (r"\bcompile\s*\(", "compile"),
    (r"\bopen\s*\(", "open"),  # نسمح بالكتابة لملفات مؤقتة فقط عبر معالجة لاحقة
    (r"\bos\.environ", "os.environ"),
    (r"\bgetpass\b", "getpass"),
    (r"\bsocket\.", "socket"),
    (r"\bctypes\b", "ctypes"),
    (r"\bcPickle\b", "cPickle"),
    (r"\bpickle\.", "pickle"),
    (r"\bmarshal\.", "marshal"),
    (r"\bimportlib\.", "importlib"),
    (r"\b__import__", "__import__"),
    (r"rm\s+-rf", "rm -rf"),
    (r";\s*rm\s+", "shell rm"),
    (r"\bchmod\b", "chmod"),
    (r"\bchown\b", "chown"),
    (r"\bsudo\b", "sudo"),
]

# imports مسموح بها فقط للكود الذاتي
_ALLOWED_IMPORTS = {
    "json", "os", "re", "math", "random", "datetime", "collections",
    "urllib", "urllib.request", "urllib.parse", "string", "itertools",
    "functools", "asyncio", "io", "textwrap", "statistics", "decimal",
    "fractions", "hashlib", "base64", "uuid", "difflib", "heapq",
    "bisect", "operator", "typing",
}


def validate_code(code: str) -> Tuple[bool, str]:
    """
    التحقق من كود AI قبل تنفيذه.
    يرجع (صالح, سبب الرفض إن وجد).
    """
    if not code or not code.strip():
        return False, "الكود فارغ"

    # فحص الأنماط الخطرة
    for pattern, name in _DANGEROUS_PATTERNS:
        if re.search(pattern, code):
            return False, f"كود خطر مكتشف: {name}"

    # فحص الـ imports
    import_lines = re.findall(r"^\s*import\s+([\w.]+)|^\s*from\s+([\w.]+)\s+import", code, re.MULTILINE)
    for match in import_lines:
        module = match[0] or match[1]
        root = module.split(".")[0]
        if root not in _ALLOWED_IMPORTS and module not in _ALLOWED_IMPORTS:
            return False, f"import غير مسموح: {module}"

    return True, "صالح"


def sanitize_input(text: str) -> str:
    """تنظيف مدخلات المستخدم قبل تمريرها للكود."""
    if not text:
        return ""
    # منع إدخال أوامر shell أو escape sequences خطرة
    text = text.replace("\x00", "").replace("\r", "")
    # تحديد الطول الأقصى
    if len(text) > 1000:
        text = text[:1000]
    return text.strip()
