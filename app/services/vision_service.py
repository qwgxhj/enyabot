"""看图服务 — 用主模型识别图片，不支持图片时降级为元数据描述。"""
from __future__ import annotations

import base64
from typing import Any

import httpx
from loguru import logger

from app.config.settings import env_settings

_PROMPT = "请仔细识别这张图片中的所有文字内容。如果有文字，逐字逐行准确输出。如果没有明显文字，请描述图片的主要内容。只输出识别结果，不要多余解释。"


async def download_image(url: str) -> bytes | None:
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            if resp.status_code == 200 and len(resp.content) > 100:
                return resp.content
    except Exception as e:
        logger.warning(f"Download image failed: {e}")
    return None


def _image_metadata(image_bytes: bytes) -> str:
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_bytes))
        w, h = img.size
        fmt = img.format or "未知"
        return f"[这是一张图片: 格式={fmt}, 尺寸={w}x{h}。当前模型不支持直接看图，请告知用户。]"
    except Exception:
        return "[用户发送了一张图片，但当前无法识别其内容。]"


async def recognize_image(image_bytes: bytes) -> str:
    """
    识别图片：
    1. 主模型 + 图片输入（需模型支持）
    2. Pillow 元数据兜底
    """
    base_url = env_settings.openai_base_url
    api_key = env_settings.openai_api_key
    model = env_settings.default_model

    if base_url and api_key and model:
        b64 = base64.b64encode(image_bytes).decode()
        payload = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": _PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }],
            "max_tokens": 1024,
        }
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{base_url.rstrip('/')}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                )
                if resp.status_code == 200:
                    content = (resp.json().get("choices") or [{}])[0].get("message", {}).get("content", "")
                    if content and content.strip():
                        return content.strip()
        except Exception as e:
            logger.warning(f"Vision API failed: {e}")

    return _image_metadata(image_bytes)


async def extract_image_text(event) -> str:
    image_urls = []
    for att in (event.attachments or []):
        if att.get("type") == "image":
            url = (att.get("data") or {}).get("url", "")
            if url:
                image_urls.append(url)
    if not image_urls:
        return ""
    results = []
    for i, url in enumerate(image_urls):
        img_bytes = await download_image(url)
        if img_bytes:
            text = await recognize_image(img_bytes)
            results.append(f"[图片{i+1}: {text}]")
        else:
            results.append(f"[图片{i+1}: 下载失败]")
    return "\n".join(results)
