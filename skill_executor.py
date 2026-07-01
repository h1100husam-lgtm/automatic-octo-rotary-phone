# ═══════════════════════════════════════════
# محرك تنفيذ الأوامر - مُحدّث
# ═══════════════════════════════════════════
from memory import (
    add_skill, add_task, add_reminder,
    save_to_long_memory, save_note, update_profile
)


async def parse_and_execute(user_id, agent_reply):
    """تحليل رد الـ AI واستخراج الأوامر وتنفيذها"""
    actions = []
    clean_reply = agent_reply

    # ═══════════════════════════════
    # 1. فحص موقع
    # ═══════════════════════════════
    if "CHECK_URL|" in agent_reply:
        try:
            from site_monitor import check_site
            from site_fixer import deep_check_site, format_site_report

            url = agent_reply.split("CHECK_URL|")[1].split("\n")[0].strip()

            if not url.startswith("http"):
                url = "https://" + url

            # فحص سريع
            quick = await check_site(url)

            # فحص عميق
            deep = await deep_check_site(url)
            report = await format_site_report(deep)

            actions.append(f"🌐 فحص الموقع: {url}")
            actions.append(f"📊 الحالة: {quick['message']}")
            actions.append(report)

            clean_reply = clean_reply.replace(f"CHECK_URL|{url}", "").strip()
        except Exception as e:
            actions.append(f"⚠️ خطأ فحص الموقع: {str(e)}")

    # ═══════════════════════════════
    # 2. بحث في الإنترنت
    # ═══════════════════════════════
    if "SEARCH|" in agent_reply:
        try:
            from web_search import search_and_format

            query = agent_reply.split("SEARCH|")[1].split("\n")[0].strip()
            result = await search_and_format(query)
            actions.append(result)

            clean_reply = clean_reply.replace(f"SEARCH|{query}", "").strip()
        except Exception as e:
            actions.append(f"⚠️ خطأ البحث: {str(e)}")

    # ═══════════════════════════════
    # 3. تنفيذ كود
    # ═══════════════════════════════
    if "RUN_CODE|" in agent_reply:
        try:
            from code_runner import execute_python_code, format_code_result

            code = agent_reply.split("RUN_CODE|")[1].split("\n")[0].strip()
            result = await execute_python_code(code)
            formatted = await format_code_result(result)
            actions.append(formatted)

            clean_reply = clean_reply.replace(f"RUN_CODE|{code}", "").strip()
        except Exception as e:
            actions.append(f"⚠️ خطأ التنفيذ: {str(e)}")

    # ═══════════════════════════════
    # 4. إضافة مهارة
    # ═══════════════════════════════
    if "ADD_SKILL|" in agent_reply:
        try:
            part = agent_reply.split("ADD_SKILL|")[1].split("\n")[0].strip()
            items = part.split("|")
            if len(items) >= 3:
                await add_skill(user_id, items[0].strip(), items[1].strip(), items[2].strip())
                actions.append(f"✅ مهارة جديدة: {items[0].strip()}")
                clean_reply = clean_reply.replace(f"ADD_SKILL|{part}", "")
        except:
            pass

    # ═══════════════════════════════
    # 5. حفظ ذاكرة
    # ═══════════════════════════════
    if "SAVE_MEMORY|" in agent_reply:
        try:
            part = agent_reply.split("SAVE_MEMORY|")[1].split("\n")[0].strip()
            items = part.split("|")
            if len(items) >= 2:
                importance = items[2].strip() if len(items) > 2 else "normal"
                await save_to_long_memory(user_id, items[0].strip(), items[1].strip(), importance)
                actions.append(f"🧠 ذاكرة: {items[1].strip()[:50]}")
                clean_reply = clean_reply.replace(f"SAVE_MEMORY|{part}", "")
        except:
            pass

    # ═══════════════════════════════
    # 6. إضافة مهمة
    # ═══════════════════════════════
    if "ADD_TASK|" in agent_reply:
        try:
            part = agent_reply.split("ADD_TASK|")[1].split("\n")[0].strip()
            items = part.split("|")
            priority = items[1].strip() if len(items) > 1 else "medium"
            await add_task(user_id, items[0].strip(), priority)
            actions.append(f"📋 مهمة: {items[0].strip()}")
            clean_reply = clean_reply.replace(f"ADD_TASK|{part}", "")
        except:
            pass

    # ═══════════════════════════════
    # 7. تذكير
    # ═══════════════════════════════
    if "ADD_REMIND|" in agent_reply:
        try:
            part = agent_reply.split("ADD_REMIND|")[1].split("\n")[0].strip()
            items = part.split("|")
            if len(items) >= 2:
                repeat = items[2].strip() if len(items) > 2 else "once"
                await add_reminder(user_id, items[1].strip(), items[0].strip(), repeat)
                actions.append(f"🔔 تذكير: {items[1].strip()}")
                clean_reply = clean_reply.replace(f"ADD_REMIND|{part}", "")
        except:
            pass

    # ═══════════════════════════════
    # 8. ملاحظة
    # ═══════════════════════════════
    if "SAVE_NOTE|" in agent_reply:
        try:
            part = agent_reply.split("SAVE_NOTE|")[1].split("\n")[0].strip()
            items = part.split("|")
            if len(items) >= 2:
                cat = items[2].strip() if len(items) > 2 else "general"
                await save_note(user_id, items[0].strip(), items[1].strip(), cat)
                actions.append(f"📝 ملاحظة: {items[0].strip()}")
                clean_reply = clean_reply.replace(f"SAVE_NOTE|{part}", "")
        except:
            pass

    # ═══════════════════════════════
    # 9. تحديث الملف
    # ═══════════════════════════════
    if "UPDATE_PROFILE|" in agent_reply:
        try:
            part = agent_reply.split("UPDATE_PROFILE|")[1].split("\n")[0].strip()
            items = part.split("|")
            kwargs = {}
            for i in range(0, len(items) - 1, 2):
                kwargs[items[i].strip()] = items[i + 1].strip()
            if kwargs:
                await update_profile(user_id, **kwargs)
                actions.append("📋 تم تحديث ملفك")
                clean_reply = clean_reply.replace(f"UPDATE_PROFILE|{part}", "")
        except:
            pass

    clean_reply = clean_reply.strip()
    if not clean_reply:
        clean_reply = "✅ تم تنفيذ طلبك!"

    return clean_reply, actions


    # ═══════════════════════════════
    # 10. بناء ميزة جديدة
    # ═══════════════════════════════
    if "BUILD_FEATURE|" in agent_reply:
        try:
            from self_builder import build_feature

            part = agent_reply.split("BUILD_FEATURE|")[1].split("\n")[0].strip()
            items = part.split("|")
            if len(items) >= 2:
                name = items[0].strip()
                desc = items[1].strip()

                success, log = await build_feature(user_id, name, desc)

                if success:
                    actions.append(f"🔧 ميزة جديدة: {name}")
                    actions.append("✅ تم بناؤها وتفعيلها!")
                else:
                    actions.append(f"❌ فشل بناء: {name}")

                clean_reply = clean_reply.replace(f"BUILD_FEATURE|{part}", "")
        except Exception as e:
            actions.append(f"⚠️ خطأ البناء: {str(e)}")

    # ═══════════════════════════════
    # 11. تشغيل ميزة مبنية
    # ═══════════════════════════════
    if "RUN_FEATURE|" in agent_reply:
        try:
            from self_builder import execute_feature

            part = agent_reply.split("RUN_FEATURE|")[1].split("\n")[0].strip()
            items = part.split("|")
            name = items[0].strip()
            data = items[1].strip() if len(items) > 1 else ""

            success, output = await execute_feature(user_id, name, data)

            if success:
                actions.append(f"⚡ نتيجة {name}:\n{output}")
            else:
                actions.append(f"❌ خطأ: {output}")

            clean_reply = clean_reply.replace(f"RUN_FEATURE|{part}", "")
        except Exception as e:
            actions.append(f"⚠️ خطأ: {str(e)}")