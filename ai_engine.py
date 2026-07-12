# ═══════════════════════════════════════════
# محرك الذكاء - مُحدّث بالكامل
# -Tool Calling Loop (بدل النصوي)
# - متعدد الموفّرين (Gemini/Groq/OpenAI)
# - شخصية ديناميكية
# ═══════════════════════════════════════════
import json
import logging
from typing import Any

from ai_providers import get_provider, AIProvider
from memory import get_history, get_profile, get_skills, get_long_memory
from personality import build_system_prompt, load_personality
from tools_registry import list_tools_schema, execute_tool
from config import MAX_TOOL_ITERATIONS

logger = logging.getLogger("agent.engine")


async def build_context(user_id: int) -> tuple[str, str, str]:
    """يبني skills_text + profile_text + memory_text للسياق."""
    skills = await get_skills(user_id)
    skills_text = (
        "\n".join([f"  ✅ {s[0]}: {s[1]}" for s in skills])
        if skills else "  لا توجد مهارات مضافة بعد"
    )

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

    memories = await get_long_memory(user_id, limit=10)
    memory_text = (
        "\n".join([f"  - [{m[0]}] {m[1]}" for m in memories])
        if memories else "  لا توجد ذكريات بعد"
    )
    return skills_text, profile_text, memory_text


async def get_smart_reply(user_id: int, user_name: str, user_message: str) -> str:
    """
    الرد الذكي مع tool calling loop:
    1. نبني الرسائل
    2. نطلب من النموذج يتكلم/يستدعي أدوات
    3. لو طلب أدوات = ننفذها ونعيد الجولة
    4. حتى يرد نص نهائي أو نصل الحد الأقصى
    """
    await load_personality()  # تحميل الشخصية من DB (مرة واحدة)

    skills_text, profile_text, memory_text = await build_context(user_id)
    system_prompt = build_system_prompt(skills_text, profile_text, memory_text, owner_name=user_name)

    # نبني history
    history = await get_history(user_id, limit=20)

    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    tools = list_tools_schema()
    provider = get_provider()

    final_text = ""
    tool_actions: list[str] = []

    for iteration in range(MAX_TOOL_ITERATIONS):
        logger.info(f"engine iteration={iteration+1} provider={provider.name}")
        try:
            response = provider.chat(messages, tools=tools, temperature=0.7, max_tokens=3000)
        except Exception as e:
            logger.exception("provider.chat failed")
            return f"⚠️ خطأ في النموذج: {e}"

        content = response.get("content", "") or ""
        tool_calls = response.get("tool_calls", []) or []

        # لو لا يوجد tool calls = رد نهائي
        if not tool_calls:
            final_text = content
            break

        # نضيف رد المساعد (لو فيه نص + tool_calls)
        assistant_msg: dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.get("id") or f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["arguments"], ensure_ascii=False) if tc.get("arguments") else "{}",
                    },
                }
                for i, tc in enumerate(tool_calls)
            ]
        messages.append(assistant_msg)

        # ننفذ كل tool call
        for tc in tool_calls:
            name = tc["name"]
            args = tc.get("arguments", {}) or {}
            logger.info(f"tool call: {name} args={list(args.keys())}")
            result = await execute_tool(name, args)

            # تسجيل صامت في logs (لا يظهر للمستخدم)
            status = "✅" if result["ok"] else "❌"
            short_args = ", ".join(f"{k}={str(v)[:30]}" for k, v in args.items() if v)
            log_line = f"🛠️ {status} {name}({short_args})"
            if not result["ok"]:
                log_line += f" → {result['error']}"
            logger.info(log_line)

            # لو فشلت الأداة = نضيف تنبيه قصير للمستخدم
            if not result["ok"]:
                tool_actions.append(f"⚠️ فشل في {name}")

            payload = result["result"] if result["ok"] else None
            error = result["error"] if not result["ok"] else None
            tool_msg_content = json.dumps(
                {"result": payload, "error": error},
                ensure_ascii=False,
                default=str,
            )[:4000]

            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id") or f"call_0",
                "name": name,
                "content": tool_msg_content,
            })

        # نكمل الجولة التالية (النموذج يكمل بناءً على نتائج الأدوات)
        # لو رجع نص ده مع(tool_calls) نستمر؛ لو رجع فقط نص(finished) = نوقف
        if iteration + 1 >= MAX_TOOL_ITERATIONS:
            final_text = content or "✅ تم التنفيذ (بلغت الحد الأقصى للمحاولات)"
            break
    else:
        final_text = final_text or "✅ تم تنفيذ طلبك!"

    # لا نُظهر للمستخدم إلا الأخطاء فقط (الفشل)
    if tool_actions:
        final_text = final_text.rstrip()
        # نضيف الأخطاء فقط (إن وُجدت) في نهاية الرد
        if any("⚠️" in a or "❌" in a for a in tool_actions):
            final_text += "\n\n" + "\n".join(tool_actions)

    return final_text
