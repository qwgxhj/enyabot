"""入群欢迎 / 自动审核插件。"""
from __future__ import annotations

import json
import time

from sqlalchemy import select

from app.db.session import db_session
from app.models.group import Group


async def set_welcome(group_platform_id: str, welcome_text: str) -> dict:
    """设置入群欢迎语。支持 {nickname}、{group_name} 变量。"""
    welcome_text = (welcome_text or "").strip()
    if not welcome_text:
        return {"success": False, "message": "欢迎语不能为空"}

    with db_session() as db:
        group = db.execute(
            select(Group).where(Group.platform_group_id == group_platform_id)
        ).scalar_one_or_none()
        if not group:
            return {"success": False, "message": "群组未注册，请先在系统中添加该群"}
        group.welcome_text = welcome_text

    return {
        "success": True,
        "message": f"欢迎语已设置：\n{welcome_text}\n\n支持变量：{{nickname}}（新人昵称）、{{group_name}}（群名）",
    }


async def get_welcome(group_platform_id: str) -> dict:
    """获取当前欢迎语。"""
    with db_session() as db:
        group = db.execute(
            select(Group).where(Group.platform_group_id == group_platform_id)
        ).scalar_one_or_none()
        if not group:
            return {"success": False, "message": "群组未注册"}
        text = group.welcome_text

    if text:
        return {"success": True, "welcome_text": text, "message": f"当前欢迎语：\n{text}"}
    return {"success": True, "welcome_text": None, "message": "当前未设置欢迎语"}


async def clear_welcome(group_platform_id: str) -> dict:
    """清除欢迎语。"""
    with db_session() as db:
        group = db.execute(
            select(Group).where(Group.platform_group_id == group_platform_id)
        ).scalar_one_or_none()
        if group:
            group.welcome_text = None
    return {"success": True, "message": "欢迎语已清除"}


# ── 验证问题系统（内存态，重启后重置） ──────────────────

# {group_platform_id: {"question": str, "answer": str}}
_verify_configs: dict[str, dict] = {}
# {group_platform_id: {user_platform_id: {"answer_time": float}}}
_pending_verifies: dict[str, dict[str, dict]] = {}

VERIFY_TIMEOUT = 300  # 5 分钟超时


async def set_verify_question(group_platform_id: str, question: str, answer: str) -> dict:
    """设置入群验证问题。"""
    question = (question or "").strip()
    answer = (answer or "").strip()
    if not question or not answer:
        return {"success": False, "message": "问题和答案不能为空"}
    _verify_configs[group_platform_id] = {"question": question, "answer": answer}
    return {"success": True, "message": f"验证问题已设置：\n问题：{question}\n答案：{answer}\n超时：{VERIFY_TIMEOUT}秒未答自动处理"}


async def check_verify(group_platform_id: str, user_platform_id: str, user_answer: str) -> dict:
    """检查入群验证答案。"""
    config = _verify_configs.get(group_platform_id)
    if not config:
        return {"success": True, "verified": True, "message": "当前无需验证"}

    if user_answer.strip() == config["answer"]:
        # 验证通过，清除待验证状态
        pending = _pending_verifies.get(group_platform_id, {})
        pending.pop(user_platform_id, None)
        return {"success": True, "verified": True, "message": "验证通过！欢迎入群~"}

    return {"success": True, "verified": False, "message": "答案不正确，请重试"}


async def on_member_join(group_platform_id: str, user_platform_id: str, nickname: str = "") -> dict:
    """新成员入群事件处理，返回需要发送的欢迎消息或验证提示。"""
    config = _verify_configs.get(group_platform_id)
    if config:
        # 需要验证
        if group_platform_id not in _pending_verifies:
            _pending_verifies[group_platform_id] = {}
        _pending_verifies[group_platform_id][user_platform_id] = {"answer_time": time.time()}
        return {
            "action": "verify",
            "message": f"欢迎 {nickname} ！请在 {VERIFY_TIMEOUT} 秒内回答以下问题：\n{config['question']}\n\n回复答案即可通过验证。",
        }

    # 无需验证，发欢迎语
    with db_session() as db:
        group = db.execute(
            select(Group).where(Group.platform_group_id == group_platform_id)
        ).scalar_one_or_none()
        welcome = group.welcome_text if group and group.welcome_text else None

    if welcome:
        text = welcome.replace("{nickname}", nickname).replace("{group_name}", group.group_name or "本群")
        return {"action": "welcome", "message": text}

    return {"action": "welcome", "message": f"欢迎 {nickname} 加入本群！🎉"}
