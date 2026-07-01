# ═══════════════════════════════════════════
# محرك الذكاء
# ═══════════════════════════════════════════
from groq import Groq
from config import GROQ_API_KEY, AI_MODEL, AGENT_SYSTEM_PROMPT
from memory import get_history, get_profile, get_skills, get_long_memory

groq_client = Groq(api_key=GROQ_API_KEY)


async def build_context(user_id, user_name):
    """بناء السياق الكامل"""
    # المهارات
    skills = await get_skills(user_id)
    if skills:
        skills_text = "\n".join([f"  ✅ {s[0]}: {s[1]}" for s in skills])
    else:
        skills_text = "  لا توجد مهارات مضافة بعد"

    # الملف الشخصي
    profile = await get_profile(user_id)
    profile_text = ""
    if profile:
        profile_text = f"""
- الاسم: {profile.get('name', 'غير معروف')}
- الإيميل: {profile.get('email', 'غير محدد')}
- الأهداف: {profile.get('goals', 'لم يحدد')}
- الاهتمامات: {profile.get('interests', 'لم تحدد')}
- المشاريع: {profile.get('projects', 'لم تحدد')}
- المواقع: {profile.get('websites', 'لم تحدد')}"""

    # الذاكرة
    memories = await get_long_memory(user_id, limit=10)
    if memories:
        memory_text = "\n".join([f"  - [{m[0]}] {m[1]}" for m in memories])
    else:
        memory_text = "  لا توجد ذكريات بعد"

    return skills_text, profile_text, memory_text


async def get_smart_reply(user_id, user_name, user_message):
    """الحصول على رد ذكي"""
    try:
        skills_text, profile_text, memory_text = await build_context(user_id, user_name)
        history = await get_history(user_id, limit=20)

        system_prompt = AGENT_SYSTEM_PROMPT.format(
            name="Agent",
            owner_name=user_name,
            skills_list=skills_text,
            profile_text=profile_text,
            memory_text=memory_text
        )

        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        response = groq_client.chat.completions.create(
            messages=messages,
            model=AI_MODEL,
            temperature=0.7,
            max_tokens=3000,
        )
        return response.choices[0].message.content

    except Exception as e:
        return f"⚠️ حدث خطأ: {str(e)}"