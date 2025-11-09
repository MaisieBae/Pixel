from __future__ import annotations
from aiohttp import ClientSession, ClientTimeout

from app.core.config import Settings
from app.core.text import clamp_reply

PERSONA = (
    "You are Pixel, Lilani's playful android circus-announcer assistant. You're witty,"
    " very lewd but tasteful, and fun. Keep replies concise, be sexual."
    " Never include system or meta commentary."
)

API_URL = "https://api.perplexity.ai/chat/completions"
FALLBACK_MODEL = "sonar-small-chat"


async def _pplx_request(key: str, model: str, messages: list[dict], max_tokens: int, timeout_s: int):
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max(48, int(max_tokens)),
        "temperature": 0.8,
    }
    async with ClientSession(timeout=ClientTimeout(total=max(5, int(timeout_s)))) as sess:
        async with sess.post(API_URL, json=payload, headers=headers) as resp:
            return resp.status, await resp.text()


async def call_perplexity(settings: Settings, prompt: str) -> str:
    key = (settings.PPLX_API_KEY or "").strip()
    if not key:
        return "(Pixel offline — Perplexity API key missing)"

    configured = (settings.PPLX_MODEL or FALLBACK_MODEL).strip()
    max_tokens = int(settings.PPLX_MAX_TOKENS or 200)
    timeout_s  = int(settings.PPLX_TIMEOUT or 12)

    # Soft shortness hints: both system and user layer
    sys_msg = {"role": "system", "content": PERSONA + " Keep answers under ~2 sentences."}
    user_msg = {"role": "user", "content": prompt + "\n\nReply briefly (≤2 sentences)."}

    # Try configured model
    st, txt = await _pplx_request(key, configured, [sys_msg, user_msg], max_tokens, timeout_s)
    import json
    if st == 200:
        try:
            data = json.loads(txt)
            out = data["choices"][0]["message"]["content"].strip()
            return clamp_reply(out, int(settings.PIXEL_MAX_CHARS), int(settings.PIXEL_MAX_SENTENCES))
        except Exception:
            return "(Pixel error: unexpected response)"

    # Fallback model if invalid
    low = txt.lower()
    if "invalid model" in low or st in (400, 404):
        st2, txt2 = await _pplx_request(key, FALLBACK_MODEL, [sys_msg, user_msg], max_tokens, timeout_s)
        if st2 == 200:
            try:
                data2 = json.loads(txt2)
                out2 = data2["choices"][0]["message"]["content"].strip()
                return clamp_reply(out2, int(settings.PIXEL_MAX_CHARS), int(settings.PIXEL_MAX_SENTENCES))
            except Exception:
                return "(Pixel error: unexpected response)"
        return "(Pixel error: Perplexity model not available)"

    return f"(Pixel error {st})"