# ═══════════════════════════════════════════
# Helpers للمستخدم الحالي
# يوفر context_local-like storage للـ user_id الحالي
# ═══════════════════════════════════════════
import contextvars

# context variable: يربط الـ user_id بـ execution الحالي
_current_user_id: contextvars.ContextVar[int | None] = contextvars.ContextVar("current_user_id", default=None)


def set_current_user_id(user_id: int) -> None:
    """ضبط المستخدم الحالي (يستدعى من handle_message)."""
    _current_user_id.set(user_id)


def current_user_id() -> int | None:
    """جلب user_id الحالي (تستخدمه الأدوات)."""
    return _current_user_id.get()
