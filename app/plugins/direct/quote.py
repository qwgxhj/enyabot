"""语录收集插件 — 收集群内有趣发言。"""
from __future__ import annotations

import random

from sqlalchemy import select, func

from app.db.session import db_session
from app.models.quote import Quote


async def add_quote(
    group_platform_id: str,
    content: str,
    added_by_platform_id: str,
    author_platform_id: str | None = None,
    author_nickname: str | None = None,
) -> dict:
    """收录一条语录。"""
    content = (content or "").strip()
    if not content:
        return {"success": False, "message": "语录内容不能为空"}

    with db_session() as db:
        quote = Quote(
            group_platform_id=group_platform_id,
            content=content,
            author_platform_id=author_platform_id,
            author_nickname=author_nickname,
            added_by_platform_id=added_by_platform_id,
        )
        db.add(quote)
        db.flush()
        quote_id = quote.id

    return {
        "success": True,
        "id": quote_id,
        "message": f"📝 语录已收录（#{quote_id}）：\n「{content}」",
    }


async def random_quote(group_platform_id: str) -> dict:
    """随机展示一条群语录。"""
    with db_session() as db:
        count = db.execute(
            select(func.count(Quote.id)).where(Quote.group_platform_id == group_platform_id)
        ).scalar() or 0

        if count == 0:
            return {"success": False, "message": "当前没有收录的语录，使用 /语录收录 <内容> 来添加"}

        # 随机偏移
        offset = random.randint(0, count - 1)
        quote = db.execute(
            select(Quote)
            .where(Quote.group_platform_id == group_platform_id)
            .offset(offset)
            .limit(1)
        ).scalar_one()

    author = f" —— {quote.author_nickname}" if quote.author_nickname else ""
    return {
        "success": True,
        "id": quote.id,
        "content": quote.content,
        "message": f"📖 #{quote.id}\n「{quote.content}」{author}",
    }


async def search_quote(group_platform_id: str, keyword: str) -> dict:
    """搜索语录。"""
    keyword = (keyword or "").strip()
    if not keyword:
        return {"success": False, "message": "搜索关键词不能为空"}

    with db_session() as db:
        quotes = db.execute(
            select(Quote)
            .where(
                Quote.group_platform_id == group_platform_id,
                Quote.content.contains(keyword),
            )
            .limit(10)
        ).scalars().all()

    if not quotes:
        return {"success": True, "results": [], "message": f"未找到包含「{keyword}」的语录"}

    lines = [f"🔍 搜索「{keyword}」找到 {len(quotes)} 条："]
    for q in quotes:
        author = f" —— {q.author_nickname}" if q.author_nickname else ""
        lines.append(f"  #{q.id} 「{q.content[:50]}{'...' if len(q.content) > 50 else ''}」{author}")

    return {
        "success": True,
        "count": len(quotes),
        "message": "\n".join(lines),
    }


async def list_quotes(group_platform_id: str, page: int = 1, page_size: int = 10) -> dict:
    """分页列出语录。"""
    offset = (page - 1) * page_size

    with db_session() as db:
        total = db.execute(
            select(func.count(Quote.id)).where(Quote.group_platform_id == group_platform_id)
        ).scalar() or 0

        quotes = db.execute(
            select(Quote)
            .where(Quote.group_platform_id == group_platform_id)
            .order_by(Quote.id.desc())
            .offset(offset)
            .limit(page_size)
        ).scalars().all()

    if not quotes:
        return {"success": True, "message": "没有更多语录了"}

    lines = [f"📖 语录列表（第 {page} 页，共 {total} 条）："]
    for q in quotes:
        author = f" —— {q.author_nickname}" if q.author_nickname else ""
        lines.append(f"  #{q.id} 「{q.content[:40]}{'...' if len(q.content) > 40 else ''}」{author}")

    return {"success": True, "count": len(quotes), "total": total, "message": "\n".join(lines)}
