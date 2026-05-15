"""群管插件 — 封装群管理相关的业务逻辑，供 Router 调用。"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.adapters.napcat_sender import NapCatSender


async def cmd_mute(sender: "NapCatSender", group_id: str, user_id: str, minutes: int) -> str:
    """禁言指定用户 minutes 分钟（0 = 解禁）。"""
    if minutes < 0 or minutes > 43200:
        return "禁言时长需在 0 ~ 43200 分钟之间（0 表示解禁）。"
    duration = minutes * 60
    result = await sender.mute_member(group_id, user_id, duration)
    if result["status"] == "ok":
        if minutes == 0:
            return f"已解除用户 {user_id} 的禁言。"
        return f"已禁言用户 {user_id} {minutes} 分钟。"
    return f"禁言失败：{result.get('raw', {}).get('msg', '未知错误')}"


async def cmd_unmute(sender: "NapCatSender", group_id: str, user_id: str) -> str:
    """解除禁言。"""
    return await cmd_mute(sender, group_id, user_id, 0)


async def cmd_kick(sender: "NapCatSender", group_id: str, user_id: str, reject: bool = False) -> str:
    """踢出群成员。"""
    result = await sender.kick_member(group_id, user_id, reject)
    if result["status"] == "ok":
        suffix = "（拒绝再次加群）" if reject else ""
        return f"已踢出用户 {user_id}{suffix}。"
    return f"踢出失败：{result.get('raw', {}).get('msg', '未知错误')}"


async def cmd_mute_all(sender: "NapCatSender", group_id: str, enable: bool = True) -> str:
    """全员禁言/解除。"""
    result = await sender.whole_ban(group_id, enable)
    if result["status"] == "ok":
        return "已开启全员禁言。" if enable else "已解除全员禁言。"
    return f"操作失败：{result.get('raw', {}).get('msg', '未知错误')}"


async def cmd_set_admin(sender: "NapCatSender", group_id: str, user_id: str, enable: bool = True) -> str:
    """设置/取消管理员。"""
    result = await sender.set_admin(group_id, user_id, enable)
    if result["status"] == "ok":
        return f"已{'设置' if enable else '取消'}用户 {user_id} 的管理员。"
    return f"操作失败：{result.get('raw', {}).get('msg', '未知错误')}"


async def cmd_set_card(sender: "NapCatSender", group_id: str, user_id: str, card: str) -> str:
    """设置群名片。"""
    result = await sender.set_card(group_id, user_id, card)
    if result["status"] == "ok":
        return f"已将用户 {user_id} 的群名片设置为：{card}"
    return f"设置失败：{result.get('raw', {}).get('msg', '未知错误')}"


async def cmd_set_title(sender: "NapCatSender", group_id: str, user_id: str, title: str) -> str:
    """设置专属头衔。"""
    result = await sender.set_special_title(group_id, user_id, title)
    if result["status"] == "ok":
        return f"已将用户 {user_id} 的专属头衔设置为：{title}"
    return f"设置失败：{result.get('raw', {}).get('msg', '未知错误')}"


async def cmd_set_group_name(sender: "NapCatSender", group_id: str, name: str) -> str:
    """修改群名。"""
    result = await sender.set_group_name(group_id, name)
    if result["status"] == "ok":
        return f"群名已修改为：{name}"
    return f"修改失败：{result.get('raw', {}).get('msg', '未知错误')}"


async def cmd_group_info(sender: "NapCatSender", group_id: str) -> str:
    """查看群信息。"""
    result = await sender.get_group_info(group_id)
    if result["status"] != "ok" or not result.get("data"):
        return "获取群信息失败。"
    info = result["data"]
    lines = [
        f"📋 群信息：{info.get('group_name', group_id)}",
        f"  群号：{info.get('group_id', group_id)}",
        f"  成员数：{info.get('member_count', '?')}/{info.get('max_member_count', '?')}",
        f"  群主：{info.get('owner_id', '?')}",
    ]
    return "\n".join(lines)


async def cmd_group_member_info(sender: "NapCatSender", group_id: str, user_id: str) -> str:
    """查看群成员信息。"""
    result = await sender.get_group_member_info(group_id, user_id)
    if result["status"] != "ok" or not result.get("data"):
        return "获取成员信息失败。"
    info = result["data"]
    role_map = {"owner": "群主", "admin": "管理员", "member": "成员"}
    role = role_map.get(info.get("role", ""), info.get("role", "未知"))
    lines = [
        f"👤 成员信息",
        f"  昵称：{info.get('nickname', '?')}",
        f"  群名片：{info.get('card', '') or '无'}",
        f"  QQ号：{info.get('user_id', user_id)}",
        f"  身份：{role}",
        f"  专属头衔：{info.get('title', '') or '无'}",
        f"  加群时间：{info.get('join_time', '?')}",
        f"  最后发言：{info.get('last_sent_time', '?')}",
    ]
    return "\n".join(lines)


async def cmd_mute_list(sender: "NapCatSender", group_id: str) -> str:
    """查看群禁言列表。"""
    result = await sender.get_group_shut_list(group_id)
    if result["status"] != "ok":
        return "获取禁言列表失败。"
    members = result.get("data") or []
    if not members:
        return "当前没有被禁言的成员。"
    lines = ["🔇 禁言列表："]
    for m in members:
        uid = m.get("user_id", "?")
        remaining = m.get("shut_up_timestamp", 0)
        if remaining > 0:
            lines.append(f"  {uid} — 剩余 {remaining} 秒")
        else:
            lines.append(f"  {uid} — 永久禁言")
    return "\n".join(lines)


# ── 兼容旧接口（供 builtin.py ToolRegistry 使用）──────────

_sender_ref = None  # 由 Router 启动时注入

def set_sender(sender):
    """注入 sender 引用，供 AI tool 调用。"""
    global _sender_ref
    _sender_ref = sender

async def mute_member(group_id: str, user_id: str, duration: int) -> dict:
    """兼容旧接口：禁言。duration 单位秒。"""
    if _sender_ref is None:
        return {"success": False, "message": "服务未就绪"}
    minutes = max(1, duration // 60)
    msg = await cmd_mute(_sender_ref, group_id, user_id, minutes)
    return {"success": True, "message": msg}

async def kick_member(group_id: str, user_id: str) -> dict:
    """兼容旧接口：踢出。"""
    if _sender_ref is None:
        return {"success": False, "message": "服务未就绪"}
    msg = await cmd_kick(_sender_ref, group_id, user_id)
    return {"success": True, "message": msg}
