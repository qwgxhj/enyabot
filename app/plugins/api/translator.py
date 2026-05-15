"""翻译插件 — 支持 DeepL / 百度翻译 / 有道翻译。"""
from __future__ import annotations

import hashlib
import random
import string
import os

import httpx
import string

# ── DeepL ──────────────────────────────────────────────
DEEPL_API_URL = "https://api-free.deepl.com/v2/translate"
DEEPL_AUTH_KEY = os.getenv("DEEPL_AUTH_KEY", "")

# ── 百度翻译 ───────────────────────────────────────────
BAIDU_APP_ID = os.getenv("BAIDU_TRANSLATE_APP_ID", "")
BAIDU_SECRET = os.getenv("BAIDU_TRANSLATE_SECRET", "")
BAIDU_API_URL = "https://fanyi-api.baidu.com/api/trans/vip/translate"

# 语言代码映射（通用 → 各平台）
LANG_MAP_DEEPL = {
    "zh": "ZH", "en": "EN", "ja": "JA", "ko": "KO",
    "fr": "FR", "de": "DE", "es": "ES", "ru": "RU",
    "auto": "",  # DeepL 自动检测
}
LANG_MAP_BAIDU = {
    "zh": "zh", "en": "en", "ja": "jp", "ko": "kor",
    "fr": "fra", "de": "de", "es": "spa", "ru": "ru",
    "auto": "auto",
}


async def _translate_deepl(text: str, target_lang: str, source_lang: str = "auto") -> dict | None:
    """调用 DeepL API，失败返回 None。"""
    if not DEEPL_AUTH_KEY:
        return None
    params: dict = {
        "auth_key": DEEPL_AUTH_KEY,
        "text": text,
        "target_lang": LANG_MAP_DEEPL.get(target_lang, target_lang.upper()),
    }
    if source_lang != "auto":
        params["source_lang"] = LANG_MAP_DEEPL.get(source_lang, source_lang.upper())
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(DEEPL_API_URL, data=params)
            resp.raise_for_status()
            data = resp.json()
        translated = data.get("translations", [{}])[0].get("text", "")
        detected = data.get("translations", [{}])[0].get("detected_source_language", "")
        return {"success": True, "translated": translated, "source_lang": detected, "engine": "deepl"}
    except Exception:
        return None


async def _translate_baidu(text: str, target_lang: str, source_lang: str = "auto") -> dict | None:
    """调用百度翻译 API，失败返回 None。"""
    if not BAIDU_APP_ID or not BAIDU_SECRET:
        return None
    salt = "".join(random.choices(string.digits, k=10))
    sign_str = BAIDU_APP_ID + text + salt + BAIDU_SECRET
    sign = hashlib.md5(sign_str.encode()).hexdigest()
    params = {
        "q": text,
        "from": LANG_MAP_BAIDU.get(source_lang, "auto"),
        "to": LANG_MAP_BAIDU.get(target_lang, target_lang),
        "appid": BAIDU_APP_ID,
        "salt": salt,
        "sign": sign,
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(BAIDU_API_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        if "error_code" in data:
            return None
        results = data.get("trans_result", [])
        translated = "\n".join(r.get("dst", "") for r in results)
        return {
            "success": True,
            "translated": translated,
            "source_lang": data.get("from", ""),
            "engine": "baidu",
        }
    except Exception:
        return None


async def translate_text(text: str, target_lang: str = "en", source_lang: str = "auto") -> dict:
    """翻译文本。优先 DeepL，回退百度翻译。"""
    if not text.strip():
        return {"success": False, "message": "待翻译文本不能为空"}
    if not target_lang:
        target_lang = "en"

    # 尝试 DeepL
    result = await _translate_deepl(text, target_lang, source_lang)
    if result and result.get("success"):
        return result

    # 回退百度翻译
    result = await _translate_baidu(text, target_lang, source_lang)
    if result and result.get("success"):
        return result

    return {
        "success": False,
        "message": "翻译失败：未配置有效的翻译 API Key（DEEPL_AUTH_KEY 或 BAIDU_TRANSLATE_APP_ID + BAIDU_TRANSLATE_SECRET）",
    }
