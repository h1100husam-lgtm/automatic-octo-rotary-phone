# ═══════════════════════════════════════════
# البحث في الإنترنت
# ═══════════════════════════════════════════
import aiohttp
import json
import logging
from urllib.parse import quote
from typing import Any

logger = logging.getLogger("agent.search")


async def search_web(query: str, num_results: int = 5) -> dict[str, Any]:
    """البحث باستخدام DuckDuckGo."""
    try:
        url = f"https://api.duckduckgo.com/?q={quote(query)}&format=json&no_html=1&skip_disambig=1"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=15),
                headers={"Accept": "application/json"},
            ) as response:
                # DuckDuckGo قد يرجع x-javascript أو text — نتقبلها
                text = await response.text()
                try:
                    data = json.loads(text)
                except Exception:
                    return {
                        "success": False,
                        "error": f"استجابة غير متوقعة: HTTP {response.status}",
                    }
                results = []

                if data.get('AbstractText'):
                    results.append({
                        'title': data.get('Heading', 'نتيجة'),
                        'snippet': data['AbstractText'],
                        'url': data.get('AbstractURL', '')
                    })

                for topic in data.get('RelatedTopics', [])[:num_results]:
                    if isinstance(topic, dict) and 'Text' in topic:
                        results.append({
                            'title': topic.get('Text', '')[:80],
                            'snippet': topic.get('Text', ''),
                            'url': topic.get('FirstURL', '')
                        })

                return {'success': True, 'query': query, 'results': results}

    except Exception as e:
        logger.exception("خطأ في search_web")
        return {'success': False, 'error': str(e)}


async def search_and_format(query: str) -> str:
    """بحث مع تنسيق النتائج كنص."""
    results = await search_web(query)

    if not results['success']:
        return f"⚠️ ما قدرت أبحث: {results['error']}"

    if not results['results']:
        return f"🔍 ما لقيت نتائج لـ: {query}\n💡 جرّب كلمات مختلفة"

    text = f"🔍 نتائج: {query}\n\n"
    for i, r in enumerate(results['results'], 1):
        text += f"📌 {i}. {r['title']}\n"
        text += f"   {r['snippet'][:150]}\n"
        if r['url']:
            text += f"   🔗 {r['url']}\n"
        text += "\n"

    return text