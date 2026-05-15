"""定时消息 / 周期性公告插件。"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from app.db.session import db_session
from app.models.scheduled_message import ScheduledMessage


async def create_scheduled_message(
    group_platform_id: str,
    creator_platform_id: str,
    content: str,
    cron_expr: str,
) -> dict:
    """创建定时消息。cron_expr 格式：分 时 日 月 周"""
    content = (content or "").strip()
    cron_expr = (cron_expr or "").strip()
    if not content:
        return {"success": False, "message": "消息内容不能为空"}
    if not cron_expr:
        return {"success": False, "message": "cron 表达式不能为空"}

    # 简单校验 cron 表达式（5 段）
    parts = cron_expr.split()
    if len(parts) != 5:
        return {"success": False, "message": "cron 表达式格式错误，应为 5 段：分 时 日 月 周\n示例：0 9 * * *（每天9点）\n示例：0 10 * * 1（每周一10点）"}

    with db_session() as db:
        msg = ScheduledMessage(
            group_platform_id=group_platform_id,
            creator_platform_id=creator_platform_id,
            content=content,
            cron_expr=cron_expr,
            enabled=True,
        )
        db.add(msg)
        db.flush()
        msg_id = msg.id

    return {
        "success": True,
        "id": msg_id,
        "message": f"定时消息已创建（#{msg_id}）\n内容：{content}\n时间：{cron_expr}",
    }


async def list_scheduled_messages(group_platform_id: str) -> dict:
    """列出群内所有定时消息。"""
    with db_session() as db:
        msgs = db.execute(
            select(ScheduledMessage)
            .where(ScheduledMessage.group_platform_id == group_platform_id)
            .order_by(ScheduledMessage.id)
        ).scalars().all()

    if not msgs:
        return {"success": True, "messages": [], "message": "当前没有定时消息"}

    lines = ["📋 定时消息列表："]
    for m in msgs:
        status = "✅ 启用" if m.enabled else "⏸ 暂停"
        lines.append(f"  #{m.id} [{status}] {m.cron_expr} → {m.content}")

    return {
        "success": True,
        "messages": [{"id": m.id, "content": m.content, "cron": m.cron_expr, "enabled": m.enabled} for m in msgs],
        "message": "\n".join(lines),
    }


async def delete_scheduled_message(msg_id: int, operator_platform_id: str) -> dict:
    """删除定时消息。"""
    with db_session() as db:
        msg = db.get(ScheduledMessage, msg_id)
        if not msg:
            return {"success": False, "message": f"定时消息 #{msg_id} 不存在"}
        db.delete(msg)

    return {"success": True, "message": f"定时消息 #{msg_id} 已删除"}


async def toggle_scheduled_message(msg_id: int, enabled: bool) -> dict:
    """启用/暂停定时消息。"""
    with db_session() as db:
        msg = db.get(ScheduledMessage, msg_id)
        if not msg:
            return {"success": False, "message": f"定时消息 #{msg_id} 不存在"}
        msg.enabled = enabled

    status = "启用" if enabled else "暂停"
    return {"success": True, "message": f"定时消息 #{msg_id} 已{status}"}
