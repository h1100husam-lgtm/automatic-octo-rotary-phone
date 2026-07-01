# ═══════════════════════════════════════════
# تحليل أخطاء المواقع
# ═══════════════════════════════════════════
import aiohttp
import asyncio


async def deep_check_site(url):
    """فحص عميق للموقع"""
    report = {'url': url, 'status': None, 'issues': [], 'performance': {}, 'security': {}}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30), allow_redirects=True) as response:
                report['status'] = response.status
                html = await response.text()

                # حجم الصفحة
                size_kb = round(len(html) / 1024, 2)
                report['performance']['size_kb'] = size_kb

                if response.status != 200:
                    report['issues'].append({'severity': 'high', 'message': f'HTTP {response.status}', 'fix': 'تحقق من السيرفر'})

                if size_kb > 5000:
                    report['issues'].append({'severity': 'medium', 'message': f'صفحة كبيرة: {size_kb} KB', 'fix': 'اضغط الصور وفعّل caching'})

                # HTTPS
                if not url.startswith('https'):
                    report['security']['https'] = False
                    report['issues'].append({'severity': 'high', 'message': 'لا يستخدم HTTPS!', 'fix': 'ثبّت SSL من Let\'s Encrypt'})
                else:
                    report['security']['https'] = True

                # عدّ الصور والسكربتات
                img_count = html.count('<img')
                script_count = html.count('<script')
                report['performance']['images'] = img_count
                report['performance']['scripts'] = script_count

                if img_count > 20:
                    report['issues'].append({'severity': 'medium', 'message': f'{img_count} صورة', 'fix': 'قلل الصور واضغطها'})

                if script_count > 15:
                    report['issues'].append({'severity': 'medium', 'message': f'{script_count} سكربت', 'fix': 'ادمج وقلل السكربتات'})

    except asyncio.TimeoutError:
        report['status'] = 'timeout'
        report['issues'].append({'severity': 'critical', 'message': 'الموقع بطيء جداً', 'fix': 'تحقق من السيرفر + CDN'})
    except Exception as e:
        report['status'] = 'error'
        report['issues'].append({'severity': 'critical', 'message': f'الموقع مطفئ: {str(e)[:80]}', 'fix': 'تحقق من الاستضافة'})

    return report


async def format_site_report(report):
    """تنسيق التقرير"""
    status_emoji = {200: "✅", 301: "↗️", 302: "↗️", 404: "❌", 500: "💥"}.get(report['status'], "❓")

    text = f"""🌐 تقرير فحص:
🔗 {report['url']}
📊 الحالة: {status_emoji} {report['status']}
📦 الحجم: {report['performance'].get('size_kb', 'N/A')} KB
🖼️ الصور: {report['performance'].get('images', 0)}
📜 السكربتات: {report['performance'].get('scripts', 0)}
🔐 HTTPS: {'✅' if report['security'].get('https') else '❌'}
"""

    if report['issues']:
        text += "\n⚠️ المشاكل:\n"
        for i, issue in enumerate(report['issues'], 1):
            e = {'critical': '🔴', 'high': '🟠', 'medium': '🟡'}.get(issue['severity'], '🟢')
            text += f"{e} {i}. {issue['message']}\n   💡 {issue['fix']}\n"
    else:
        text += "\n✅ لا توجد مشاكل! 🎉"

    return text