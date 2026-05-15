"""媒体解析插件 — 支持抖音/快手/B站等平台视频解析。"""
from __future__ import annotations

import re

import httpx

_MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
_DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def _extract_text(html: str, pattern: str, default: str = "") -> str:
    m = re.search(pattern, html, re.DOTALL)
    return m.group(1).strip() if m else default


# ── B站解析 ──────────────────────────────────────────────

_BV_RE = re.compile(r"(BV[a-zA-Z0-9]{10})")
_AV_RE = re.compile(r"(?:av|AV)(\d+)")


async def _parse_bilibili(url: str) -> dict:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        headers = {"User-Agent": _DESKTOP_UA, "Referer": "https://www.bilibili.com/"}

        if "b23.tv" in url:
            try:
                resp = await client.get(url, headers=headers)
                url = str(resp.url)
            except Exception:
                return {"success": False, "message": "B站短链解析失败。"}

        bvid = None
        m = _BV_RE.search(url)
        if m:
            bvid = m.group(1)
        else:
            m = _AV_RE.search(url)
            if m:
                resp = await client.get(
                    "https://api.bilibili.com/x/web-interface/view",
                    params={"aid": int(m.group(1))}, headers=headers,
                )
                data = resp.json().get("data")
                if data:
                    bvid = data.get("bvid")
        if not bvid:
            return {"success": False, "message": "无法从链接中提取B站视频ID。"}

        resp = await client.get(
            "https://api.bilibili.com/x/web-interface/view",
            params={"bvid": bvid}, headers=headers,
        )
        result = resp.json()
        if result.get("code") != 0:
            return {"success": False, "message": f"B站API错误: {result.get('message', '')}"}
        info = result["data"]
        title = info.get("title", "未知标题")
        author = info.get("owner", {}).get("name", "未知")
        cover = info.get("pic", "")
        if cover and not cover.startswith("http"):
            cover = "https:" + cover
        duration = info.get("duration", 0)
        view = info.get("stat", {}).get("view", 0)
        like = info.get("stat", {}).get("like", 0)
        cid = info.get("cid", 0)

        # fnval=0 获取音视频合流的 durl 格式
        play_url = ""
        try:
            play_resp = await client.get(
                "https://api.bilibili.com/x/player/playurl",
                params={"bvid": bvid, "cid": cid, "qn": 80, "fnval": 0},
                headers=headers,
            )
            play_data = play_resp.json().get("data", {})
            durl = play_data.get("durl")
            if durl:
                play_url = durl[0].get("url", "")
        except Exception:
            pass

    minutes, seconds = divmod(duration, 60)
    lines = [
        f"📺 {title}",
        f"👤 UP主: {author}",
        f"⏱ {minutes:02d}:{seconds:02d}  ▶ {view:,}  👍 {like:,}",
        f"🔗 https://www.bilibili.com/video/{bvid}",
    ]
    if play_url:
        lines.append("📥 播放地址已获取")

    return {
        "success": True, "platform": "bilibili",
        "title": title, "author": author, "cover": cover,
        "play_url": play_url, "url": f"https://www.bilibili.com/video/{bvid}",
        "message": "\n".join(lines),
    }


# ── 抖音解析 ─────────────────────────────────────────────

_DY_ID_RE = re.compile(r"/video/(\d+)")
_DY_NOTE_RE = re.compile(r"/note/(\d+)")


async def _parse_douyin(url: str) -> dict:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        if "v.douyin.com" in url:
            try:
                resp = await client.get(url, headers={"User-Agent": _MOBILE_UA})
                url = str(resp.url)
            except Exception:
                return {"success": False, "message": "抖音短链解析失败。"}

        video_id = None
        m = _DY_ID_RE.search(url)
        if m:
            video_id = m.group(1)
        else:
            m = _DY_NOTE_RE.search(url)
            if m:
                video_id = m.group(1)
        if not video_id:
            m = re.search(r"/(\d{15,})", url)
            if m:
                video_id = m.group(1)
        if not video_id:
            return {"success": False, "message": "无法从链接中提取抖音视频ID。"}

        play_url = desc = author = cover = ""
        duration = digg = 0

        # 方案1：移动端分享页 _ROUTER_DATA（最可靠）
        try:
            resp = await client.get(
                f"https://m.douyin.com/share/video/{video_id}",
                headers={"User-Agent": _MOBILE_UA},
            )
            html = resp.text
            router_m = re.search(
                r'window\._ROUTER_DATA\s*=\s*(\{.*?\})\s*;?\s*</script>', html, re.DOTALL,
            )
            if router_m:
                data_str = router_m.group(1).replace('\\u002F', '/')
                desc = _extract_text(data_str, r'"desc"\s*:\s*"([^"]*)"')
                author = _extract_text(data_str, r'"nickname"\s*:\s*"([^"]*)"')
                cover = _extract_text(data_str, r'"cover"[\s\S]*?"url_list"\s*:\s*\["([^"]*)"')
                # 在 url_list 中找 playwm 视频链接
                for ul in re.findall(r'"url_list"\s*:\s*\[(.*?)\]', data_str):
                    for u in re.findall(r'"(https?://[^"]*)"', ul):
                        if 'playwm' in u or ('aweme' in u and '/play' in u):
                            play_url = u.replace('playwm', 'play')
                            break
                    if play_url:
                        break
        except Exception:
            pass

        # 方案2：iesdouyin API
        if not desc:
            try:
                resp = await client.get(
                    f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={video_id}",
                    headers={"User-Agent": _DESKTOP_UA, "Referer": "https://www.douyin.com/"},
                )
                items = resp.json().get("item_list") or []
                if items:
                    item = items[0]
                    desc = item.get("desc", "")
                    author = item.get("author", {}).get("nickname", "")
                    cover = (item.get("video", {}).get("cover", {}).get("url_list") or [""])[0]
                    if not play_url:
                        play_url = (item.get("video", {}).get("play_addr", {}).get("url_list") or [""])[0]
                        if play_url:
                            play_url = play_url.replace("playwm", "play")
                    duration = item.get("duration", 0) // 1000
                    digg = item.get("statistics", {}).get("digg_count", 0)
            except Exception:
                pass

        # 方案3：douyin.com SSR
        if not desc:
            try:
                resp = await client.get(
                    f"https://www.douyin.com/video/{video_id}",
                    headers={"User-Agent": _DESKTOP_UA, "Referer": "https://www.douyin.com/"},
                )
                html = resp.text
                ssr = re.search(r'<script id="RENDER_DATA"[^>]*>(.*?)</script>', html, re.DOTALL)
                if ssr:
                    import urllib.parse
                    decoded = urllib.parse.unquote(ssr.group(1))
                    desc = _extract_text(decoded, r'"desc"\s*:\s*"([^"]*)"') or desc
                    author = _extract_text(decoded, r'"nickname"\s*:\s*"([^"]*)"') or author
            except Exception:
                pass

    if not desc:
        desc = "抖音视频"

    minutes, seconds = divmod(duration, 60)
    lines = [f"🎵 {desc}"]
    if author:
        lines.append(f"👤 {author}")
    if duration > 0:
        lines.append(f"⏱ {minutes:02d}:{seconds:02d}  👍 {digg:,}")
    lines.append(f"🔗 https://www.douyin.com/video/{video_id}")
    if play_url:
        lines.append("📥 无水印地址已获取")

    return {
        "success": True, "platform": "douyin",
        "title": desc, "author": author, "cover": cover,
        "play_url": play_url, "url": f"https://www.douyin.com/video/{video_id}",
        "message": "\n".join(lines),
    }


# ── 快手解析 ─────────────────────────────────────────────

async def _parse_kuaishou(url: str) -> dict:
    if "v.kuaishou.com" in url:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            try:
                resp = await client.get(url, headers={"User-Agent": _MOBILE_UA})
                url = str(resp.url)
            except Exception:
                return {"success": False, "message": "快手短链解析失败。"}

    headers = {"User-Agent": _DESKTOP_UA, "Referer": "https://www.kuaishou.com/"}
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        try:
            resp = await client.get(url, headers=headers)
            html = resp.text
            title = _extract_text(html, r'"caption"\s*:\s*"([^"]*)"') or "快手视频"
            author = _extract_text(html, r'"userName"\s*:\s*"([^"]*)"')
            play_url = _extract_text(html, r'"photoUrl"\s*:\s*"([^"]*)"')

            lines = [f"🎬 {title}"]
            if author:
                lines.append(f"👤 {author}")
            lines.append(f"🔗 {url}")
            if play_url:
                lines.append("📥 播放地址已获取")

            return {
                "success": True, "platform": "kuaishou",
                "title": title, "author": author,
                "play_url": play_url, "url": url,
                "message": "\n".join(lines),
            }
        except Exception as e:
            return {"success": False, "message": f"快手解析失败: {e}"}


# ── 统一入口 ─────────────────────────────────────────────

async def media_parse(url: str) -> dict:
    url = (url or "").strip()
    if not url:
        return {"success": False, "message": "链接不能为空"}

    # 从文本中提取第一个 URL
    urls = re.findall(r'https?://\S+', url)
    if urls:
        url = urls[0].rstrip('，。,.')

    if any(domain in url for domain in ["bilibili.com", "b23.tv"]):
        return await _parse_bilibili(url)
    elif any(domain in url for domain in ["douyin.com", "iesdouyin.com"]):
        return await _parse_douyin(url)
    elif "kuaishou.com" in url:
        return await _parse_kuaishou(url)
    else:
        return {
            "success": False,
            "message": f"暂不支持该链接的解析。\n目前支持: B站、抖音、快手\n链接: {url}",
        }
