# ═══════════════════════════════════════════
# مراقبة المواقع
# ═══════════════════════════════════════════
import aiohttp
import asyncio
from memory import get_sites, update_site_status, add_site_error


async def check_site(url):
    """فحص موقع واحد"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    return {"status": "ok", "code": 200, "message": "✅ الموقع شغّال"}
                else:
                    return {"status": "error", "code": response.status, "message": f"⚠️ خطأ {response.status}"}
    except asyncio.TimeoutError:
        return {"status": "timeout", "code": None, "message": "⏰ الموقع بطيء جداً"}
    except Exception as e:
        return {"status": "down", "code": None, "message": f"❌ الموقع مطفئ: {str(e)[:100]}"}


async def monitor_all_sites(user_id):
    """فحص كل المواقع"""
    sites = await get_sites(user_id)
    results = []

    for site in sites:
        site_id, url, name, interval, last_status, is_active = site
        if not is_active:
            continue

        result = await check_site(url)
        current_status = result['status']
        await update_site_status(site_id, current_status)

        if last_status == "ok" and current_status != "ok":
            await add_site_error(user_id, site_id, current_status, result['message'], url, result.get('code'))
            results.append({"site": name, "url": url, "alert": True, "message": result['message']})
        else:
            results.append({"site": name, "url": url, "alert": False, "message": result['message']})

    return results