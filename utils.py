# ═══════════════════════════════════════════
# أدوات مساعدة
# ═══════════════════════════════════════════
import secrets
import string
from typing import Optional


def generate_password(length: int = 16, use_special: bool = True) -> tuple[str, str]:
    """توليد كلمة مرور قوية. يرجع (كلمة_المرور, تقييم_القوة)."""
    chars = string.ascii_letters + string.digits
    if use_special:
        chars += "!@#$%^&*"
    password = ''.join(secrets.choice(chars) for _ in range(length))

    if length >= 16 and use_special:
        strength = "قوية جداً 💪"
    elif length >= 12:
        strength = "قوية ✅"
    else:
        strength = "متوسطة ⚠️"

    return password, strength


def generate_qr(text: str, filename: str = "qr.png") -> Optional[str]:
    """توليد QR Code كصورة. يرجع المسار أو None."""
    try:
        import qrcode
        img = qrcode.make(text)
        img.save(filename)
        return filename
    except ImportError:
        return None


async def shorten_url(url: str) -> dict[str, object]:
    """تقصير رابط عبر tinyurl."""
    try:
        import pyshorteners
        s = pyshorteners.Shortener()
        short = s.tinyurl.short(url)
        return {'success': True, 'short': short}
    except Exception as e:
        return {'success': False, 'error': str(e)}