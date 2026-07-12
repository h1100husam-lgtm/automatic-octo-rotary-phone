# ═══════════════════════════════════════════
# نظام الشخصية الديناميكية
# - الاسم، النبرة، الجنس، الأسلوب قابلة للتعديل وقت التشغيل
# - يحفظ في DB (bot_config) ليبقى بعد إعادة التشغيل
# - يُبنى معه system_prompt ديناميكياً
# ═══════════════════════════════════════════
import json
import logging
import aiosqlite
from pathlib import Path
from config import (
    AGENT_NAME, AGENT_GENDER, AGENT_TONE, AGENT_LOCALE,
    GENDER_LABELS, TONE_LABELS, DB_PATH, AGENT_SYSTEM_PROMPT,
)

logger = logging.getLogger("agent.personality")


# الحالة الحالية (تُحمّل من DB)
_state: dict = {
    "name": AGENT_NAME,
    "gender": AGENT_GENDER,
    "tone": AGENT_TONE,
    "locale": AGENT_LOCALE,
    "custom_instructions": "",
}


async def load_personality() -> None:
    """تحميل الشخصية من DB عند بدء التشغيل."""
    global _state
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS bot_config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            async with db.execute("SELECT value FROM bot_config WHERE key='personality'") as c:
                row = await c.fetchone()
                if row:
                    saved = json.loads(row[0])
                    _state.update(saved)
        logger.info(f"✅ شخصية الـ Agent: {current_name()} | {current_gender_label()}")
    except Exception as e:
        logger.error(f"تعذّر تحميل الشخصية: {e}")


async def save_personality() -> None:
    """حفظ الشخصية الحالية في DB."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO bot_config (key, value) VALUES ('personality', ?)",
                (json.dumps(_state, ensure_ascii=False),),
            )
            await db.commit()
    except Exception as e:
        logger.error(f"تعذّر حفظ الشخصية: {e}")


def update_personality(
    name=None, gender=None, tone=None,
    locale=None, custom_instructions=None,
) -> dict:
    """تحديث الحقول الممررة فقط. ثم حفظ غير متزامن."""
    changes = []
    if name and isinstance(name, str):
        _state["name"] = name.strip()[:40]
        changes.append("name")
    if gender in ("female", "male", "neutral"):
        _state["gender"] = gender
        changes.append("gender")
    if tone in ("friendly", "formal", "casual", "professional"):
        _state["tone"] = tone
        changes.append("tone")
    if locale:
        _state["locale"] = locale
        changes.append("locale")
    if custom_instructions is not None:
        _state["custom_instructions"] = custom_instructions[:2000]
        changes.append("custom_instructions")
    # حفظ غير متزامن (نطلقه ولا ننتظره)
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(save_personality())
    except RuntimeError:
        pass  # لا loop متاح
    logger.info(f"تم تحديث الشخصية: {changes}")
    return {"changed": changes, "current": current_state()}


def current_state() -> dict:
    return dict(_state)


def current_name() -> str:
    return _state.get("name", AGENT_NAME)


def current_gender_label() -> str:
    return GENDER_LABELS.get(_state.get("gender", AGENT_GENDER), "محايد")


def current_tone_label() -> str:
    return TONE_LABELS.get(_state.get("tone", AGENT_TONE), "ودودة")


def build_system_prompt(skills_text, profile_text, memory_text, owner_name) -> str:
    """يبني system_prompt ديناميكياً مع الشخصية الحالية + التعليمات المخصصة."""
    name = current_name()
    gender_label = current_gender_label()
    tone_label = current_tone_label()

    prompt = AGENT_SYSTEM_PROMPT.format(
        name=name,
        owner_name=owner_name or "صديقي",
        gender_label=gender_label,
        tone_label=tone_label,
        skills_list=skills_text or "لا توجد مهارات بعد",
        profile_text=profile_text or "لا يوجد ملف بعد",
        memory_text=memory_text or "لا توجد ذكريات بعد",
    )

    custom = _state.get("custom_instructions", "")
    if custom:
        prompt += f"\n\n═════════════════════════\n📝 تعليمات شخصية إضافية:\n═════════════════════════\n{custom}\n"

    return prompt
