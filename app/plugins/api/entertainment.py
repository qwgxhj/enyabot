from __future__ import annotations

import httpx


SUPERPOWER_API_URL = "https://api-v2.yuafeng.cn/API/sup_power.php"
KFC_API_URL = "https://api-v2.yuafeng.cn/API/kfc.php"


async def random_superpower() -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(SUPERPOWER_API_URL)
        response.raise_for_status()
        text = response.text.strip()

    return {
        "success": True,
        "raw": text,
        "message": text or "接口返回为空",
    }


async def kfc_crazy_thursday() -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(KFC_API_URL)
        response.raise_for_status()
        text = response.text.strip()

    return {
        "success": True,
        "raw": text,
        "message": text or "接口返回为空",
    }
