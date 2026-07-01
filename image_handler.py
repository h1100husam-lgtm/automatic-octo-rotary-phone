# ═══════════════════════════════════════════
# تحليل الصور
# ═══════════════════════════════════════════
import os
import base64


async def analyze_image(image_path, user_query=""):
    """تحليل الصورة باستخدام Groq Vision"""
    try:
        from groq import Groq
        from config import GROQ_API_KEY

        client = Groq(api_key=GROQ_API_KEY)

        # تحميل وتحويل الصورة
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        # نوع الصورة
        ext = os.path.splitext(image_path)[1].lower()
        mime_map = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif', '.webp': 'image/webp'}
        mime = mime_map.get(ext, 'image/jpeg')

        query = user_query if user_query else "اشرح لي محتوى هذه الصورة بالتفصيل بالعربي"

        response = client.chat.completions.create(
            model="llama-3.2-90b-vision-preview",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_data}"}},
                    {"type": "text", "text": query}
                ]
            }],
            max_tokens=2000
        )

        return f"🖼️ **تحليل الصورة:**\n\n{response.choices[0].message.content}"

    except Exception as e:
        return f"⚠️ ما قدرت أحلل الصورة: {str(e)}"