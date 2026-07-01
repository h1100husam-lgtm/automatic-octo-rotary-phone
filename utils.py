# ═══════════════════════════════════════════
# أدوات مساعدة
# ═══════════════════════════════════════════
import secrets
import string


def generate_password(length=16, use_special=True):
    """توليد كلمة مرور قوية"""
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


def generate_qr(text, filename="qr.png"):
    """توليد QR Code"""
    try:
        import qrcode
        img = qrcode.make(text)
        img.save(filename)
        return filename
    except ImportError:
        return None


async def shorten_url(url):
    """تقصير رابط"""
    try:
        import pyshorteners
        s = pyshorteners.Shortener()
        short = s.tinyurl.short(url)
        return {'success': True, 'short': short}
    except Exception as e:
        return {'success': False, 'error': str(e)}