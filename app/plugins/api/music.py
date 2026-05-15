"""音乐点歌插件 — 网易云音乐搜索（多源 fallback）。"""
from __future__ import annotations

import os
import time

import httpx

# ── API 源列表（按优先级排列） ──────────────────────────
# 可通过环境变量 NETEASE_API_BASE 覆盖第一个源
CUSTOM_API = os.getenv("NETEASE_API_BASE", "").strip()

SEARCH_SOURCES = [
    # 源 1：自定义（如果配了环境变量）
    *(({"name": "custom", "url": CUSTOM_API, "type": "meting"},) if CUSTOM_API else ()),
    # 源 2：网易云官方搜索接口（最可靠）
    {"name": "official", "url": "https://music.163.com/api/search/get", "type": "official"},
    # 源 3：Vercel 部署的 NeteaseCloudMusicApi（备用）
    {"name": "netease-api-1", "url": "https://netease-cloud-music-api-psi-six.vercel.app/", "type": "vercel"},
    {"name": "netease-api-2", "url": "https://cloud-music-api-fe.vercel.app/", "type": "vercel"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://music.163.com/",
}


async def _search_meting(url: str, keyword: str, limit: int) -> list[dict] | None:
    """Meting API 搜索格式。"""
    try:
        async with httpx.AsyncClient(timeout=8, headers=HEADERS) as client:
            resp = await client.get(url, params={"type": "search", "s": keyword, "limit": limit})
            resp.raise_for_status()
            data = resp.json()
        if not isinstance(data, list):
            return None
        songs = []
        for item in data:
            songs.append({
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "artist": item.get("artist", item.get("author", "")),
                "album": item.get("album", ""),
                "url": item.get("url", ""),
                "pic": item.get("pic", ""),
            })
        return songs if songs else None
    except Exception:
        return None


async def _search_vercel(url: str, keyword: str, limit: int) -> list[dict] | None:
    """Vercel 部署的 NeteaseCloudMusicApi 搜索格式。"""
    try:
        search_url = f"{url.rstrip('/')}/search"
        async with httpx.AsyncClient(timeout=8, headers=HEADERS) as client:
            resp = await client.get(search_url, params={"keywords": keyword, "limit": limit})
            resp.raise_for_status()
            data = resp.json()
        result = data.get("result", {})
        songs_data = result.get("songs", [])
        if not songs_data:
            return None
        songs = []
        for item in songs_data:
            artists = "、".join(a.get("name", "") for a in item.get("artists", []))
            album_name = (item.get("album") or {}).get("name", "")
            songs.append({
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "artist": artists,
                "album": album_name,
                "url": "",
                "pic": "",
            })
        return songs if songs else None
    except Exception:
        return None


async def _search_official(keyword: str, limit: int) -> list[dict] | None:
    """网易云官方搜索接口。"""
    try:
        async with httpx.AsyncClient(timeout=8, headers=HEADERS) as client:
            resp = await client.post(
                "https://music.163.com/api/search/get",
                data={"s": keyword, "type": 1, "limit": limit, "offset": 0},
            )
            resp.raise_for_status()
            data = resp.json()
        result = data.get("result", {})
        songs_data = result.get("songs", [])
        if not songs_data:
            return None
        songs = []
        for item in songs_data:
            artists = "、".join(a.get("name", "") for a in item.get("artists", []))
            album_name = (item.get("album") or {}).get("name", "")
            songs.append({
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "artist": artists,
                "album": album_name,
                "url": "",
                "pic": "",
            })
        return songs if songs else None
    except Exception:
        return None


async def search_music(keyword: str, limit: int = 3) -> dict:
    """搜索音乐，多源自动 fallback。"""
    keyword = (keyword or "").strip()
    if not keyword:
        return {"success": False, "message": "歌曲关键词不能为空"}

    errors = []
    for source in SEARCH_SOURCES:
        try:
            if source["type"] == "meting":
                songs = await _search_meting(source["url"], keyword, limit)
            elif source["type"] == "vercel":
                songs = await _search_vercel(source["url"], keyword, limit)
            elif source["type"] == "official":
                songs = await _search_official(keyword, limit)
            else:
                continue

            if songs:
                return {
                    "success": True,
                    "count": len(songs),
                    "songs": songs,
                    "source": source["name"],
                    "message": f"找到 {len(songs)} 首歌曲",
                }
        except Exception as e:
            errors.append(f"{source['name']}: {e}")

    return {
        "success": False,
        "message": f"所有音乐源均不可用。请检查网络或配置 NETEASE_API_BASE 环境变量。\n错误详情：{'; '.join(errors[-3:])}",
    }


async def get_song_url(song_id: str) -> dict:
    """获取歌曲播放链接，尝试多种方式。"""
    song_id = (song_id or "").strip()
    if not song_id:
        return {"success": False, "message": "歌曲 ID 不能为空"}

    # 方式 1：Vercel 实例
    for source in SEARCH_SOURCES:
        if source["type"] != "vercel":
            continue
        try:
            url = f"{source['url'].rstrip('/')}/song/url"
            async with httpx.AsyncClient(timeout=8, headers=HEADERS) as client:
                resp = await client.get(url, params={"id": song_id})
                resp.raise_for_status()
                data = resp.json()
            song_data = data.get("data", [])
            if song_data and song_data[0].get("url"):
                return {"success": True, "url": song_data[0]["url"], "message": "获取成功"}
        except Exception:
            continue

    # 方式 2：网易云官方外链（部分歌曲可直接播放/下载）
    outer_url = f"https://music.163.com/song/media/outer/url?id={song_id}.mp3"
    try:
        async with httpx.AsyncClient(timeout=8, headers=HEADERS, follow_redirects=True) as client:
            resp = await client.head(outer_url)
            content_type = resp.headers.get("content-type", "")
            if "audio" in content_type or "mpeg" in content_type:
                return {"success": True, "url": str(resp.url), "message": "获取成功"}
    except Exception:
        pass

    # 方式 3：返回外链地址（NapCat 可能能直接播放）
    return {"success": True, "url": outer_url, "message": "获取成功（外链）"}


# ── 搜索缓存（用于选歌） ───────────────────────────────
# {group_id: {"keyword": str, "songs": list, "time": float}}
_search_cache: dict[str, dict] = {}
CACHE_TTL = 300  # 5 分钟过期


def _get_cache_key(group_id: str | None, user_id: str) -> str:
    return group_id or user_id


async def search_and_cache(keyword: str, group_id: str | None, user_id: str, limit: int = 5) -> dict:
    """搜索并缓存结果，返回格式化消息。"""
    result = await search_music(keyword, limit)
    if not result["success"]:
        return result

    cache_key = _get_cache_key(group_id, user_id)
    _search_cache[cache_key] = {
        "keyword": keyword,
        "songs": result["songs"],
        "time": time.time(),
    }

    lines = [f"🎵 搜索「{keyword}」{result['message']}："]
    for i, song in enumerate(result["songs"], 1):
        album = f" · {song['album']}" if song.get('album') else ""
        lines.append(f"  {i}. {song['name']} — {song['artist']}{album}")
    lines.append("")
    lines.append("回复 /选歌 <编号> 获取歌曲详情")

    return {
        "success": True,
        "count": result["count"],
        "message": "\n".join(lines),
    }


async def select_song(index: int, group_id: str | None, user_id: str) -> dict:
    """根据编号选择歌曲，返回详情和链接。"""
    cache_key = _get_cache_key(group_id, user_id)
    cached = _search_cache.get(cache_key)

    if not cached or time.time() - cached["time"] > CACHE_TTL:
        return {"success": False, "message": "没有搜索记录或已过期，请先用 /点歌 歌名 搜索"}

    songs = cached["songs"]
    if index < 1 or index > len(songs):
        return {"success": False, "message": f"编号无效，请输入 1~{len(songs)}"}

    song = songs[index - 1]

    # 尝试获取播放链接
    url_info = await get_song_url(str(song["id"]))
    play_url = url_info.get("url", "") if url_info["success"] else ""

    lines = [f"🎵 {song['name']}"]
    lines.append(f"  歌手：{song['artist']}")
    if song.get("album"):
        lines.append(f"  专辑：{song['album']}")
    lines.append(f"  ID：{song['id']}")
    if play_url:
        lines.append(f"  链接：{play_url}")
    else:
        lines.append(f"  链接：https://music.163.com/#/song?id={song['id']}")

    return {
        "success": True,
        "song": song,
        "play_url": play_url,
        "message": "\n".join(lines),
    }
