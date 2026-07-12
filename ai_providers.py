# ═══════════════════════════════════════════
# نظام الموفّرين المتعدّد (Multi-Provider)
# يدعم: Gemini + Groq + OpenAI + قابل للتمدد
# ═══════════════════════════════════════════
import os
from typing import Any, Optional
from config import (
    GROQ_API_KEY, AI_MODEL, GEMINI_API_KEY,
    OPENAI_API_KEY, AI_PROVIDER,
)
import logging

logger = logging.getLogger("agent.providers")


class AIProvider:
    """الواجهة الأساسية لأي موفّر ذكاء اصطناعي."""

    name: str = "base"

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 3000,
    ) -> dict[str, Any]:
        """يرجع استجابة بشكل موحّد: {content, tool_calls, raw}."""
        raise NotImplementedError

    def transcribe(self, audio_path: str) -> str:
        """تحويل الصوت لنص (للـ providers اللي تدعم)."""
        raise NotImplementedError

    def tts(self, text: str, voice: str = "default") -> bytes:
        """تحويل النص لصوت (للـ providers اللي تدعم)."""
        raise NotImplementedError


# ═══════════════════════════════════════════
# 1. Groq Provider (سريع، مجاني)
# ═══════════════════════════════════════════
class GroqProvider(AIProvider):
    name = "groq"

    def __init__(self, api_key: str, model: str):
        try:
            from groq import Groq
            self.client = Groq(api_key=api_key)
            self.model = model
        except ImportError as e:
            raise RuntimeError("groq SDK غير مثبت. ثبته بـ: pip install groq") from e

    def chat(self, messages, tools=None, temperature=0.7, max_tokens=3000):
        try:
            kwargs = {
                "messages": messages,
                "model": self.model,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            response = self.client.chat.completions.create(**kwargs)
            choice = response.choices[0].message

            tool_calls = []
            if choice.tool_calls:
                import json
                for tc in choice.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments)
                    except Exception:
                        args = {}
                    tool_calls.append({
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": args,
                    })

            return {
                "content": choice.content or "",
                "tool_calls": tool_calls,
                "raw": response,
                "provider": self.name,
            }
        except Exception as e:
            logger.exception("Groq chat error")
            return {"content": f"⚠️ خطأ في Groq: {e}", "tool_calls": [], "raw": None, "provider": self.name}

    def transcribe(self, audio_path: str) -> str:
        try:
            from groq import Groq
            with open(audio_path, "rb") as f:
                response = self.client.audio.transcriptions.create(
                    file=f,
                    model="whisper-large-v3",
                )
            return response.text
        except Exception as e:
            logger.exception("Groq transcribe error")
            return ""


# ═══════════════════════════════════════════
# 2. Gemini Provider (مميز بالبرو، احسن في الذكاء)
# ═══════════════════════════════════════════
class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self.genai = genai
            self.model = model
        except ImportError as e:
            raise RuntimeError("google-generativeai غير مثبت. "
                                "ثبته بـ: pip install google-generativeai") from e

    def chat(self, messages, tools=None, temperature=0.7, max_tokens=3000):
        try:
            # تحويل messages إلى تنسيق Gemini
            contents = []
            system_text = ""
            for m in messages:
                if m["role"] == "system":
                    system_text += m["content"] + "\n"
                elif m["role"] == "user":
                    contents.append({"role": "user", "parts": [m["content"]]})
                elif m["role"] == "assistant":
                    contents.append({"role": "model", "parts": [m["content"]]})

            model = self.genai.GenerativeModel(
                self.model,
                system_instruction=system_text if system_text else None,
            )

            # دفع أدوات (_tools) كـ function declarations (دعم Gemini)
            genai_tools = None
            if tools:
                try:
                    decls = []
                    for t in tools:
                        if t.get("type") == "function" and "function" in t:
                            decls.append(t["function"])
                    if decls:
                        genai_tools = [{"function_declarations": decls}]
                except Exception:
                    genai_tools = None

            gen_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            }

            kwargs = {"generation_config": gen_config}
            if genai_tools:
                kwargs["tools"] = genai_tools

            # نتكلم واحدة واحدة للحفاظ على السياق
            response = model.generate_content(contents, **kwargs)
            text = getattr(response, "text", "") or ""

            # استخراج tool calls من Gemini (لو موجودة)
            tool_calls = []
            try:
                candidates = getattr(response, "candidates", []) or []
                if candidates:
                    parts = getattr(candidates[0].content, "parts", []) or []
                    for part in parts:
                        fc = getattr(part, "function_call", None)
                        if fc:
                            tool_calls.append({
                                "id": "",
                                "name": getattr(fc, "name", ""),
                                "arguments": dict(getattr(fc, "args", {}) or {}),
                            })
            except Exception:
                pass

            return {
                "content": text,
                "tool_calls": tool_calls,
                "raw": response,
                "provider": self.name,
            }
        except Exception as e:
            logger.exception("Gemini chat error")
            return {"content": f"⚠️ خطأ في Gemini: {e}", "tool_calls": [], "raw": None, "provider": self.name}


# ═══════════════════════════════════════════
# 3. OpenAI Provider (للـ TTS والـ Realtime لاحقاً)
# ═══════════════════════════════════════════
class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
            self.model = model
        except ImportError as e:
            raise RuntimeError("openai SDK غير مثبت. ثبته بـ: pip install openai") from e

    def chat(self, messages, tools=None, temperature=0.7, max_tokens=3000):
        try:
            kwargs = {
                "messages": messages,
                "model": self.model,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            response = self.client.chat.completions.create(**kwargs)
            choice = response.choices[0].message

            tool_calls = []
            if choice.tool_calls:
                import json
                for tc in choice.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments)
                    except Exception:
                        args = {}
                    tool_calls.append({
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": args,
                    })

            return {
                "content": choice.content or "",
                "tool_calls": tool_calls,
                "raw": response,
                "provider": self.name,
            }
        except Exception as e:
            logger.exception("OpenAI chat error")
            return {"content": f"⚠️ خطأ في OpenAI: {e}", "tool_calls": [], "raw": None, "provider": self.name}

    def tts(self, text: str, voice: str = "alloy") -> bytes:
        try:
            response = self.client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text,
            )
            return response.content
        except Exception as e:
            logger.exception("OpenAI TTS error")
            return b""


# ═══════════════════════════════════════════
# الـ Registry: يبني الموفّر المناسب حسب الإعداد
# ═══════════════════════════════════════════
def build_provider(provider_name: Optional[str] = None) -> AIProvider:
    """يبني provider حسب الاسم أو إعداد AI_PROVIDER."""
    name = (provider_name or AI_PROVIDER or "groq").lower()

    if name == "gemini":
        if not GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY غير محدد - سيتم التراجع إلى Groq")
            return build_provider("groq")
        return GeminiProvider(GEMINI_API_KEY, model="gemini-2.5-flash")

    if name == "openai":
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY غير محدد")
        return OpenAIProvider(OPENAI_API_KEY)

    # default: groq
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY غير محدد")
    return GroqProvider(GROQ_API_KEY, AI_MODEL)


# Singleton (default)
_default_provider: Optional[AIProvider] = None


def get_provider() -> AIProvider:
    global _default_provider
    if _default_provider is None:
        _default_provider = build_provider()
    return _default_provider


def set_provider(name: str):
    """تبديل الـ provider وقت التشغيل (لو المستخدم يدّعم)."""
    global _default_provider
    _default_provider = build_provider(name)
    return _default_provider
