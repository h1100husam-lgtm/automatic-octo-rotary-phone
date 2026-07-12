# ════════════════════════════════════════════
# نظام الشخصية الديناميكية
# - الاسم، النبرة، الجنس، الأسلوب قابلة للتعديل وقت التشغيل
# - يحفظ في DB (bot_config) ليبقى بعد إعادة التشغيل
# - يُبنى معه system_prompt ديناميكياً
# ════════════════════════════════════════════
import json
import logging
from pathlib import Path
from config import (
    AGENT_NAME, AGENT_GENDER, AGENT_TONE, AGENT_LOCALE,
    GENDER_LABELS, TONE_LABELS, DB_TYPE
)

logger = logging.getLogger("agent.personality")

# Database pool imports
from db_pool import get_db_connection

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


async def _fetchval(query: str, *args):
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
        async with get_db_connection() as conn:
            # Ensure table exists
            if DB_TYPE == "postgresql":
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS bot_config (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
            else:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS bot_config (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
                await conn.commit()
            # Fetch personality
            row = await _fetchone("SELECT value FROM bot_config WHERE key='personality'")
            if row:
                saved = json.loads(row[0])
                _state.update(saved)
        logger.info(f"✅ شخصية الـ Agent: {current_name()} | {current_gender_label()}")
    except Exception as e:
        logger.error(f"تعذّر تحميل الشخصية: {e}")


async def save_personality() -> None:
    """حفظ الشخصية الحالية في DB."""
    try:
        async with get_db_connection() as conn:
            if DB_TYPE == "postgresql":
                await conn.execute(
                    "INSERT INTO bot_config (key, value) VALUES ($1, $2) "
                    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                    "personality", json.dumps(_state, ensure_ascii=False)
                )
            else:
                await conn.execute(
                    "INSERT OR REPLACE INTO bot_config (key, value) VALUES (?, ?)",
                    ("personality", json.dumps(_state, ensure_ascii=False))
                )
                await conn.commit()
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