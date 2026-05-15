from __future__ import annotations

import httpx


API_URL = "https://api-v2.yuafeng.cn/API/name_duplicate_query.php"
API_KEY = "ccc6b4dee999ba948960f0d1e838b3cae72062001b854df49b22d2bf9875f171"


async def name_duplicate_query(name: str) -> dict:
    name = (name or "").strip()
    if not name:
        return {"success": False, "message": "姓名不能为空"}

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(API_URL, params={"name": name, "apikey": API_KEY})
        response.raise_for_status()
        text = response.text.strip()

    return {
        "success": True,
        "name": name,
        "raw": text,
        "message": text or "接口返回为空",
    }
