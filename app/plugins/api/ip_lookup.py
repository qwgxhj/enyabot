from __future__ import annotations

import httpx


API_URL = "https://api-v2.yuafeng.cn/API/ip_location.php"
API_TOKEN = "ccc6b4dee999ba948960f0d1e838b3cae72062001b854df49b22d2bf9875f171"


async def ip_location_query(ip: str) -> dict:
    ip = (ip or "").strip()
    if not ip:
        return {"success": False, "message": "IP 不能为空"}

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(API_URL, params={"ip": ip, "type": API_TOKEN})
        response.raise_for_status()
        text = response.text.strip()

    return {
        "success": True,
        "ip": ip,
        "raw": text,
        "message": text or "接口返回为空",
    }
