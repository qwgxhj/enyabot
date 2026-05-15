"""趣味作图插件 — 调用在线 API 生成趣味图片。"""
from __future__ import annotations

import re
from typing import Any

import httpx
from loguru import logger


# ── 作图 API 配置 ─────────────────────────────────────────
# 占位符说明：
#   {qq}     → 目标用户QQ号
#   {myqq}   → 发送者QQ号
#   {name}   → 目标用户群昵称
#   {text}   → 用户输入的文字
#   {url}    → 用户头像URL

_AVATAR_URL = "http://q1.qlogo.cn/g?b=qq&s=640&nk={qq}"

IMAGE_APIS: dict[str, dict[str, Any]] = {
    # ── 头像类 ──
    "查看头像": {"url": "http://q1.qlogo.cn/g?b=qq&s=640&nk={qq}", "desc": "查看QQ头像", "type": "avatar"},
    "头像框":   {"url": "https://api.andeer.top/API/headimg.php?qq={qq}", "desc": "头像相框", "type": "avatar"},
    "高清头像": {"url": "https://api.andeer.top/API/gzl.php?qq={qq}", "desc": "高清头像", "type": "avatar"},
    "举牌":     {"url": "https://api.zxz.ee/api/jupai/?type=img&url={url}", "desc": "举牌图片", "type": "avatar"},

    # ── 文字类 ──
    "群主说":   {"url": "https://api.tangdouz.com/wz/qunshuo.php?qq={qq}&nr={text}&sf=群主&name={name}", "desc": "群主发言图", "type": "text", "need_text": True},
    "管理说":   {"url": "https://api.tangdouz.com/wz/qunshuo.php?qq={qq}&nr={text}&sf=管理员&name={name}", "desc": "管理员发言图", "type": "text", "need_text": True},
    "群员说":   {"url": "https://api.tangdouz.com/wz/qunshuo.php?qq={qq}&nr={text}&sf=群员&name={name}", "desc": "群员发言图", "type": "text", "need_text": True},
    "恶搞":     {"url": "http://api.tangdouz.com/wz/py.php?nr={text}&q={qq}", "desc": "恶搞P图", "type": "text", "need_text": True},

    # ── 趣味类（单人）──
    "2爱":      {"url": "http://api.tangdouz.com/wz/pa.php?q={qq}", "desc": "比心", "type": "single"},
    "想":       {"url": "http://api.tangdouz.com/wz/think.php?q={qq}", "desc": "想想", "type": "single"},
    "2牌":      {"url": "http://api.tangdouz.com/wz/qian.php?q={myqq}&qq={qq}", "desc": "抽牌", "type": "single"},
    "看蛋人":   {"url": "https://free.wqwlkj.cn/wqwlapi/dan.php?qq={qq}", "desc": "蛋人画像", "type": "single"},
    "教我写代码": {"url": "https://free.wqwlkj.cn/wqwlapi/jwxdm.php?qq={qq}", "desc": "教我写代码", "type": "single"},
    "给我安排": {"url": "https://free.wqwlkj.cn/wqwlapi/anpai.php?qq={qq}", "desc": "安排一下", "type": "single"},
    "买吧不贵": {"url": "https://free.wqwlkj.cn/wqwlapi/mbbg.php?qq={qq}", "desc": "买买买", "type": "single"},
    "在做人吗": {"url": "https://free.wqwlkj.cn/wqwlapi/klzzl.php?qq={qq}", "desc": "在做人吗", "type": "single"},
    "2素描":    {"url": "https://api.xingzhige.com/API/xian/?url={url}", "desc": "素描头像", "type": "avatar"},
    "镜像":     {"url": "https://oiapi.net/API/MirrorImage?url={url}", "desc": "镜像翻转", "type": "avatar"},
    "冰淇淋":   {"url": "https://oiapi.net/API/IceCream/", "desc": "随机冰淇淋", "type": "random"},
    "踢":       {"url": "https://api.andeer.top/API/img_tr.php?qq={qq}", "desc": "踢人", "type": "single"},
    "动爬":     {"url": "https://api.andeer.top/API/img_climb.php?qq={qq}", "desc": "爬", "type": "single"},
    "日记":     {"url": "https://api.andeer.top/API/img_tg.php?qq={qq}", "desc": "日记", "type": "single"},
    "羡慕":     {"url": "https://api.andeer.top/API/xianmu.php?qq={qq}", "desc": "羡慕", "type": "single"},
    "地图":     {"url": "https://api.andeer.top/API/dt.php?qq={qq}", "desc": "地图", "type": "single"},
    "搬砖":     {"url": "https://api.andeer.top/API/banzhuan.php?qq={qq}", "desc": "搬砖", "type": "single"},
    "甘雨爱心": {"url": "https://api.andeer.top/API/img_love.php?qq={qq}", "desc": "甘雨爱心", "type": "single"},
    "蒙娜丽莎": {"url": "https://api.andeer.top/API/img_mnls.php?qq={qq}", "desc": "蒙娜丽莎", "type": "single"},

    # ── 双人互动类 ──
    "2可达鸭":  {"url": "https://api.andeer.top/API/gif_duck.php?bqq={myqq}&cqq={qq}", "desc": "可达鸭互动", "type": "double"},
    "洗头":     {"url": "https://api.andeer.top/API/moca.php?cqq={myqq}&bqq={qq}", "desc": "洗头互动", "type": "double"},

    # ── 名片类 ──
    "随机名片": {"url": "https://api.zxz.ee/api/qqgxmp/?qq={qq}&qid=5201314&name={name}&type=", "desc": "随机名片", "type": "card"},
    **{f"{i}名片": {"url": f"https://api.zxz.ee/api/qqgxmp/?qq={{qq}}&qid=5201314&name={{name}}&type={i}", "desc": f"名片样式{i}", "type": "card"} for i in range(1, 13)},
}


def _build_url(api_info: dict, qq: str, myqq: str, name: str, text: str) -> str:
    """根据 API 配置和参数构建请求 URL。"""
    url = api_info["url"]
    avatar = _AVATAR_URL.format(qq=qq)
    url = url.replace("{qq}", str(qq))
    url = url.replace("{myqq}", str(myqq))
    url = url.replace("{name}", name or str(qq))
    url = url.replace("{text}", text or "")
    url = url.replace("{url}", avatar)
    return url


async def generate_image(cmd: str, qq: str, myqq: str, name: str = "", text: str = "") -> dict:
    """
    调用作图 API 生成图片。
    返回 {"success": bool, "image_url": str, "message": str}
    """
    api_info = IMAGE_APIS.get(cmd)
    if not api_info:
        available = ", ".join(sorted(IMAGE_APIS.keys()))
        return {"success": False, "message": f"未知作图命令: {cmd}\n可用命令: {available}"}

    if api_info.get("need_text") and not text:
        return {"success": False, "message": f"用法: /作图 {cmd} <文字内容>"}

    url = _build_url(api_info, qq, myqq, name, text)

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                content_type = resp.headers.get("content-type", "")
                if "image" in content_type or len(resp.content) > 1000:
                    return {"success": True, "image_url": url, "message": api_info["desc"]}
                # 返回的可能是 JSON 错误
                return {"success": False, "message": f"API 返回非图片内容"}
            return {"success": False, "message": f"API 返回 {resp.status_code}"}
    except Exception as e:
        logger.warning(f"作图 API 调用失败: {cmd}, {e}")
        return {"success": False, "message": f"作图失败: {e}"}


def list_image_commands() -> str:
    """列出所有可用的作图命令。"""
    lines = ["🎨 可用作图命令：\n"]

    categories: dict[str, list[str]] = {}
    for name, info in IMAGE_APIS.items():
        cat = info.get("type", "other")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(f"  {name} — {info['desc']}")

    cat_names = {
        "avatar": "🖼️ 头像类",
        "text": "📝 文字类（需要文字参数）",
        "single": "🎭 趣味类",
        "double": "👥 双人互动",
        "card": "💳 名片类",
        "random": "🎲 随机类",
    }

    for cat, items in categories.items():
        lines.append(cat_names.get(cat, cat))
        lines.extend(items)
        lines.append("")

    return "\n".join(lines)
