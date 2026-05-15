"""搜图 / 以图搜图插件 — SauceNAO + TraceMoe。"""
from __future__ import annotations

import os

import httpx

SAUCENAO_API_URL = "https://saucenao.com/search.php"
SAUCENAO_API_KEY = os.getenv("SAUCENAO_API_KEY", "")

TRACEMOE_API_URL = "https://trace.moe/api/search"


async def _search_saucenao(image_url: str, num_results: int = 3) -> list[dict]:
    """SauceNAO 搜图，返回结果列表，失败返回空列表。"""
    if not SAUCENAO_API_KEY:
        return []
    params = {
        "api_key": SAUCENAO_API_KEY,
        "output_type": 2,  # JSON
        "numres": num_results,
        "url": image_url,
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(SAUCENAO_API_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        results = []
        for item in data.get("results", []):
            header = item.get("header", {})
            info = item.get("data", {})
            similarity = header.get("similarity", "0")
            results.append({
                "similarity": f"{similarity}%",
                "source": info.get("source", info.get("title", "未知")),
                "author": info.get("member_name", info.get("author_name", "未知")),
                "url": info.get("ext_urls", [info.get("source", "")])[0] if info.get("ext_urls") else info.get("source", ""),
                "engine": "saucenao",
            })
        return results
    except Exception:
        return []


async def _search_tracemoe(image_url: str) -> list[dict]:
    """TraceMoe 搜图（动画截图），返回结果列表，失败返回空列表。"""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(TRACEMOE_API_URL, params={"url": image_url})
            resp.raise_for_status()
            data = resp.json()
        results = []
        for item in data.get("result", [])[:3]:
            anilist = item.get("anilist", 0)
            episode = item.get("episode", "?")
            start = item.get("start", 0)
            similarity = item.get("similarity", 0)
            # 格式化时间
            mins, secs = divmod(int(start), 60)
            results.append({
                "similarity": f"{similarity * 100:.1f}%",
                "anilist_id": anilist,
                "episode": episode,
                "timestamp": f"{mins:02d}:{secs:02d}",
                "url": f"https://anilist.co/anime/{anilist}",
                "preview": item.get("image", ""),
                "engine": "tracemoe",
            })
        return results
    except Exception:
        return []


async def image_search(image_url: str) -> dict:
    """以图搜图。优先 SauceNAO，同时尝试 TraceMoe。"""
    if not image_url.strip():
        return {"success": False, "message": "图片 URL 不能为空"}

    saucenao_results = await _search_saucenao(image_url)
    tracemoe_results = await _search_tracemoe(image_url)

    all_results = saucenao_results + tracemoe_results

    if not all_results:
        return {
            "success": False,
            "message": "未找到匹配结果。请确认已配置 SAUCENAO_API_KEY，或图片链接可访问。",
        }

    return {
        "success": True,
        "count": len(all_results),
        "results": all_results,
        "message": f"找到 {len(all_results)} 条结果",
    }
