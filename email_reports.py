# ═══════════════════════════════════════════
# توليد التقارير
# ═══════════════════════════════════════════
from memory import get_full_stats, get_tasks, get_site_errors


async def generate_daily_report(user_id, user_name):
    """إنشاء تقرير يومي"""
    stats = await get_full_stats(user_id)
    pending = await get_tasks(user_id, "pending")
    errors = await get_site_errors(user_id, limit=5)

    report = f"""📊 التقرير اليومي - {user_name}
═══════════════════════════

💬 الرسائل: {stats['messages']}
📋 مهام معلقة: {stats['pending_tasks']}
✅ مهام منجزة: {stats['done_tasks']}
🧠 مهارات: {stats['skills']}
📝 ملاحظات: {stats['notes']}
🔔 تذكيرات: {stats['active_reminders']}
🌐 مواقع: {stats['monitored_sites']}
💾 ذكريات: {stats['memories']}

═══════════════════════════
📋 المهام المعلقة:
"""
    if pending:
        for t in pending:
            report += f"  🔴 {t[1]} (أولوية: {t[2]})\n"
    else:
        report += "  🎉 لا توجد مهام معلقة\n"

    if errors:
        report += "\n⚠️ آخر الأخطاء:\n"
        for e in errors:
            report += f"  ❌ {e[0]} - {str(e[2])[:50]}\n"

    report += "\n═══════════════════════════"
    return report