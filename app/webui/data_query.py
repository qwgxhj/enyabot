"""WebUI 数据查询辅助模块。"""
from __future__ import annotations

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.vote import Vote, VoteRecord
from app.models.quote import Quote
from app.models.countdown import Countdown
from app.models.scheduled_message import ScheduledMessage
from app.models.calendar_event import CalendarEvent
from app.models.keyword_rule import KeywordRule
from app.models.user import User
from app.models.group import Group
from app.models.reminder import Reminder


def get_stats() -> dict:
    """获取数据库统计数据。"""
    try:
        with SessionLocal() as db:
            return {
                "users": db.execute(select(func.count(User.id))).scalar() or 0,
                "groups": db.execute(select(func.count(Group.id))).scalar() or 0,
                "votes": db.execute(select(func.count(Vote.id))).scalar() or 0,
                "quotes": db.execute(select(func.count(Quote.id))).scalar() or 0,
                "countdowns": db.execute(select(func.count(Countdown.id))).scalar() or 0,
                "scheduled_msgs": db.execute(select(func.count(ScheduledMessage.id))).scalar() or 0,
                "calendar_events": db.execute(select(func.count(CalendarEvent.id))).scalar() or 0,
                "keyword_rules": db.execute(select(func.count(KeywordRule.id))).scalar() or 0,
                "reminders": db.execute(select(func.count(Reminder.id))).scalar() or 0,
            }
    except Exception:
        return {"users": 0, "groups": 0, "votes": 0, "quotes": 0,
                "countdowns": 0, "scheduled_msgs": 0, "calendar_events": 0,
                "keyword_rules": 0, "reminders": 0}


def list_votes(limit: int = 20) -> list[dict]:
    """列出投票。"""
    try:
        with SessionLocal() as db:
            votes = db.execute(select(Vote).order_by(Vote.id.desc()).limit(limit)).scalars().all()
            result = []
            import json
            for v in votes:
                options = json.loads(v.options) if v.options else []
                vote_count = db.execute(
                    select(func.count(VoteRecord.id)).where(VoteRecord.vote_id == v.id)
                ).scalar() or 0
                result.append({
                    "id": v.id,
                    "question": v.question,
                    "options": options,
                    "status": v.status,
                    "vote_count": vote_count,
                    "group_id": v.group_platform_id,
                    "created_at": v.created_at.strftime("%Y-%m-%d %H:%M") if v.created_at else "",
                })
            return result
    except Exception:
        return []


def list_quotes_data(limit: int = 20) -> list[dict]:
    """列出语录。"""
    try:
        with SessionLocal() as db:
            quotes = db.execute(select(Quote).order_by(Quote.id.desc()).limit(limit)).scalars().all()
            return [{
                "id": q.id,
                "content": q.content[:60],
                "author": q.author_nickname or "-",
                "group_id": q.group_platform_id,
                "created_at": q.created_at.strftime("%Y-%m-%d %H:%M") if q.created_at else "",
            } for q in quotes]
    except Exception:
        return []


def list_countdowns_data(limit: int = 20) -> list[dict]:
    """列出倒数日。"""
    from datetime import date
    try:
        with SessionLocal() as db:
            cds = db.execute(select(Countdown).order_by(Countdown.target_date).limit(limit)).scalars().all()
            today = date.today()
            return [{
                "id": c.id,
                "name": c.name,
                "target_date": str(c.target_date),
                "days_left": (c.target_date - today).days,
                "group_id": c.group_platform_id,
                "remind_daily": c.remind_daily,
            } for c in cds]
    except Exception:
        return []


def list_scheduled_msgs_data(limit: int = 20) -> list[dict]:
    """列出定时消息。"""
    try:
        with SessionLocal() as db:
            msgs = db.execute(select(ScheduledMessage).order_by(ScheduledMessage.id.desc()).limit(limit)).scalars().all()
            return [{
                "id": m.id,
                "content": m.content[:40],
                "cron_expr": m.cron_expr,
                "enabled": m.enabled,
                "group_id": m.group_platform_id,
            } for m in msgs]
    except Exception:
        return []


def list_keyword_rules_data(limit: int = 30) -> list[dict]:
    """列出关键词规则。"""
    import json
    try:
        with SessionLocal() as db:
            rules = db.execute(select(KeywordRule).order_by(KeywordRule.id.desc()).limit(limit)).scalars().all()
            result = []
            for r in rules:
                replies = json.loads(r.replies) if r.replies else []
                result.append({
                    "id": r.id,
                    "pattern": r.pattern,
                    "is_regex": r.is_regex,
                    "replies_count": len(replies),
                    "cooldown": r.cooldown_seconds,
                    "enabled": r.enabled,
                    "group_id": r.group_platform_id,
                })
            return result
    except Exception:
        return []


def list_calendar_events_data(limit: int = 20) -> list[dict]:
    """列出日程事件。"""
    try:
        with SessionLocal() as db:
            events = db.execute(
                select(CalendarEvent).order_by(CalendarEvent.event_time.desc()).limit(limit)
            ).scalars().all()
            return [{
                "id": e.id,
                "title": e.title,
                "event_time": e.event_time.strftime("%Y-%m-%d %H:%M") if e.event_time else "",
                "location": e.location or "-",
                "reminded": e.reminded,
                "group_id": e.group_platform_id,
            } for e in events]
    except Exception:
        return []
