"""增强版关键词插件 — 支持正则、随机回复、冷却时间。"""
from __future__ import annotations

import json
import re
import time
from collections import defaultdict

from sqlalchemy import select

from app.db.session import db_session
from app.models.keyword_rule import KeywordRule

# 冷却记录：{(group_id, rule_id): last_trigger_time}
_cooldown_map: dict[tuple[str, int], float] = {}


async def add_keyword_rule(
    group_platform_id: str,
    creator_platform_id: str,
    pattern: str,
    replies_str: str,
    is_regex: bool = False,
    cooldown_seconds: int = 0,
) -> dict:
    """添加关键词规则。replies_str 格式：回复1 | 回复2 | 回复3"""
    pattern = (pattern or "").strip()
    replies_str = (replies_str or "").strip()
    if not pattern:
        return {"success": False, "message": "关键词不能为空"}
    if not replies_str:
        return {"success": False, "message": "回复内容不能为空"}

    # 校验正则
    if is_regex:
        try:
            re.compile(pattern)
        except re.error as e:
            return {"success": False, "message": f"正则表达式语法错误：{e}"}

    replies = [r.strip() for r in replies_str.split("|") if r.strip()]
    if not replies:
        return {"success": False, "message": "回复内容不能为空"}

    with db_session() as db:
        rule = KeywordRule(
            group_platform_id=group_platform_id,
            pattern=pattern,
            is_regex=is_regex,
            replies=json.dumps(replies, ensure_ascii=False),
            cooldown_seconds=cooldown_seconds,
            enabled=True,
            creator_platform_id=creator_platform_id,
        )
        db.add(rule)
        db.flush()
        rule_id = rule.id

    mode = "正则" if is_regex else "精确"
    random_note = f"（{len(replies)} 条随机回复）" if len(replies) > 1 else ""
    cd_note = f"，冷却 {cooldown_seconds}秒" if cooldown_seconds > 0 else ""

    return {
        "success": True,
        "id": rule_id,
        "message": f"关键词规则已添加（#{rule_id}）\n模式：{mode}，匹配：{pattern}{random_note}{cd_note}",
    }


async def list_keyword_rules(group_platform_id: str) -> dict:
    """列出群内关键词规则。"""
    with db_session() as db:
        rules = db.execute(
            select(KeywordRule)
            .where(KeywordRule.group_platform_id == group_platform_id)
            .order_by(KeywordRule.id)
        ).scalars().all()

    if not rules:
        return {"success": True, "rules": [], "message": "当前没有关键词规则"}

    lines = ["📋 关键词规则列表："]
    for r in rules:
        mode = "正则" if r.is_regex else "精确"
        status = "✅" if r.enabled else "⏸"
        replies = json.loads(r.replies)
        lines.append(f"  {status} #{r.id} [{mode}] {r.pattern} → {replies[0][:20]}{'...' if len(replies[0]) > 20 else ''}")

    return {
        "success": True,
        "rules": [{"id": r.id, "pattern": r.pattern, "is_regex": r.is_regex} for r in rules],
        "message": "\n".join(lines),
    }


async def delete_keyword_rule(rule_id: int) -> dict:
    """删除关键词规则。"""
    with db_session() as db:
        rule = db.get(KeywordRule, rule_id)
        if not rule:
            return {"success": False, "message": f"规则 #{rule_id} 不存在"}
        db.delete(rule)

    return {"success": True, "message": f"规则 #{rule_id} 已删除"}


async def match_keyword(group_platform_id: str, message_text: str) -> str | None:
    """匹配关键词，返回回复内容（或 None）。供消息路由层调用。"""
    now = time.time()

    with db_session() as db:
        rules = db.execute(
            select(KeywordRule).where(
                KeywordRule.group_platform_id == group_platform_id,
                KeywordRule.enabled == True,
            )
        ).scalars().all()

    for rule in rules:
        matched = False
        if rule.is_regex:
            try:
                matched = bool(re.search(rule.pattern, message_text))
            except re.error:
                continue
        else:
            matched = rule.pattern in message_text

        if not matched:
            continue

        # 冷却检查
        cd_key = (group_platform_id, rule.id)
        if rule.cooldown_seconds > 0:
            last = _cooldown_map.get(cd_key, 0)
            if now - last < rule.cooldown_seconds:
                continue

        _cooldown_map[cd_key] = now

        # 随机选一条回复
        replies = json.loads(rule.replies)
        import random
        return random.choice(replies)

    return None
