"""群聊摘要插件 — AI 生成群消息总结。"""
from __future__ import annotations

from sqlalchemy import select, desc

from app.db.session import db_session
from app.models.message_log import MessageLog


async def get_recent_messages(group_platform_id: str, limit: int = 50) -> list[dict]:
    """从数据库拉取最近 N 条群消息。"""
    with db_session() as db:
        # 假设 MessageLog 有 group_platform_id, sender_nickname, content, created_at 字段
        # 如果表结构不同，需要调整
        try:
            messages = db.execute(
                select(MessageLog)
                .where(MessageLog.group_id == group_platform_id)
                .order_by(desc(MessageLog.created_at))
                .limit(limit)
            ).scalars().all()
            messages.reverse()  # 按时间正序

            return [
                {
                    "sender": getattr(m, "user_id", "未知"),
                    "content": getattr(m, "raw_text", ""),
                    "time": getattr(m, "created_at", None),
                }
                for m in messages
            ]
        except Exception:
            return []


async def summarize_chat(group_platform_id: str, limit: int = 50) -> dict:
    """生成群聊摘要。返回消息列表供 AI 处理。"""
    messages = await get_recent_messages(group_platform_id, limit)

    if not messages:
        return {
            "success": False,
            "message": "没有找到最近的群消息记录",
        }

    # 格式化消息为文本
    chat_lines = []
    for msg in messages:
        sender = msg.get("sender", "未知")
        content = msg.get("content", "")
        chat_lines.append(f"{sender}: {content}")

    chat_text = "\n".join(chat_lines)

    return {
        "success": True,
        "message_count": len(messages),
        "chat_text": chat_text,
        "message": f"已获取最近 {len(messages)} 条消息，请使用 AI 生成摘要",
        "prompt_hint": "请总结以下群聊内容，提取主要话题、关键结论和待办事项：\n\n" + chat_text,
    }
