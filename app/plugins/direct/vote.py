"""群投票/问卷插件。"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select, func

from app.db.session import db_session
from app.models.vote import Vote, VoteRecord


async def create_vote(
    group_platform_id: str,
    creator_platform_id: str,
    question: str,
    options_str: str,
    anonymous: bool = False,
) -> dict:
    """创建投票。options_str 格式：选项1 | 选项2 | 选项3"""
    question = (question or "").strip()
    options_str = (options_str or "").strip()
    if not question:
        return {"success": False, "message": "投票问题不能为空"}
    if not options_str:
        return {"success": False, "message": "选项不能为空，格式：选项1 | 选项2 | 选项3"}

    options = [o.strip() for o in options_str.split("|") if o.strip()]
    if len(options) < 2:
        return {"success": False, "message": "至少需要 2 个选项"}
    if len(options) > 10:
        return {"success": False, "message": "最多 10 个选项"}

    with db_session() as db:
        vote = Vote(
            group_platform_id=group_platform_id,
            creator_platform_id=creator_platform_id,
            question=question,
            options=json.dumps(options, ensure_ascii=False),
            anonymous=anonymous,
            status="open",
        )
        db.add(vote)
        db.flush()
        vote_id = vote.id

    options_display = "\n".join(f"  {i+1}. {opt}" for i, opt in enumerate(options))
    return {
        "success": True,
        "vote_id": vote_id,
        "question": question,
        "options": options,
        "message": f"投票已创建（#{vote_id}）\n{question}\n{options_display}\n\n回复 /投票 {vote_id} <选项编号> 参与投票",
    }


async def cast_vote(vote_id: int, voter_platform_id: str, option_index: int) -> dict:
    """参与投票。option_index 从 1 开始。"""
    with db_session() as db:
        vote = db.get(Vote, vote_id)
        if not vote:
            return {"success": False, "message": f"投票 #{vote_id} 不存在"}
        if vote.status != "open":
            return {"success": False, "message": f"投票 #{vote_id} 已关闭"}

        options = json.loads(vote.options)
        if option_index < 1 or option_index > len(options):
            return {"success": False, "message": f"选项编号无效，请输入 1-{len(options)}"}

        # 检查是否已投票
        existing = db.execute(
            select(VoteRecord).where(
                VoteRecord.vote_id == vote_id,
                VoteRecord.voter_platform_id == voter_platform_id,
            )
        ).scalar_one_or_none()
        if existing:
            return {"success": False, "message": "你已经投过票了"}

        record = VoteRecord(
            vote_id=vote_id,
            voter_platform_id=voter_platform_id,
            option_index=option_index - 1,  # 存储为 0-indexed
        )
        db.add(record)

    return {
        "success": True,
        "message": f"投票成功！你选择了：{options[option_index - 1]}",
    }


async def vote_result(vote_id: int) -> dict:
    """查看投票结果。"""
    with db_session() as db:
        vote = db.get(Vote, vote_id)
        if not vote:
            return {"success": False, "message": f"投票 #{vote_id} 不存在"}

        options = json.loads(vote.options)
        # 统计各选项票数
        counts = db.execute(
            select(VoteRecord.option_index, func.count(VoteRecord.id))
            .where(VoteRecord.vote_id == vote_id)
            .group_by(VoteRecord.option_index)
        ).all()

        total = sum(c for _, c in counts)
        count_map = {idx: cnt for idx, cnt in counts}

        lines = [f"📊 {vote.question}", f"状态：{'进行中' if vote.status == 'open' else '已结束'}", f"总票数：{total}", ""]
        for i, opt in enumerate(options):
            cnt = count_map.get(i, 0)
            pct = f"{cnt / total * 100:.0f}%" if total > 0 else "0%"
            bar = "█" * int(cnt / max(total, 1) * 20)
            lines.append(f"  {i+1}. {opt}  {bar} {cnt}票 ({pct})")

    return {
        "success": True,
        "vote_id": vote_id,
        "total_votes": total,
        "message": "\n".join(lines),
    }


async def close_vote(vote_id: int, creator_platform_id: str) -> dict:
    """关闭投票（仅创建者可操作）。"""
    with db_session() as db:
        vote = db.get(Vote, vote_id)
        if not vote:
            return {"success": False, "message": f"投票 #{vote_id} 不存在"}
        if vote.creator_platform_id != creator_platform_id:
            return {"success": False, "message": "只有创建者可以关闭投票"}
        if vote.status != "open":
            return {"success": False, "message": "投票已经关闭了"}

        vote.status = "closed"
        vote.closed_at = datetime.utcnow()

    return {"success": True, "message": f"投票 #{vote_id} 已关闭"}
