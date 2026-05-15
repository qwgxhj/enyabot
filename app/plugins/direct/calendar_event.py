"""日程 / 日历事件插件。"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.db.session import db_session
from app.models.calendar_event import CalendarEvent


async def add_event(
    creator_platform_id: str,
    title: str,
    event_time_str: str,
    group_platform_id: str | None = None,
    location: str = "",
    description: str = "",
    remind_before_min: int = 30,
) -> dict:
    """添加日程事件。event_time_str 格式：YYYY-MM-DD HH:MM"""
    title = (title or "").strip()
    event_time_str = (event_time_str or "").strip()
    if not title:
        return {"success": False, "message": "事件标题不能为空"}
    if not event_time_str:
        return {"success": False, "message": "时间不能为空，格式：YYYY-MM-DD HH:MM"}

    try:
        event_time = datetime.strptime(event_time_str, "%Y-%m-%d %H:%M")
    except ValueError:
        return {"success": False, "message": "时间格式错误，正确格式：YYYY-MM-DD HH:MM\n例如：2026-05-15 14:00"}

    with db_session() as db:
        event = CalendarEvent(
            group_platform_id=group_platform_id,
            creator_platform_id=creator_platform_id,
            title=title,
            event_time=event_time,
            location=location or None,
            description=description or None,
            remind_before_min=remind_before_min,
        )
        db.add(event)
        db.flush()
        event_id = event.id

    parts = [f"📅 日程已添加（#{event_id}）", f"  标题：{title}", f"  时间：{event_time_str}"]
    if location:
        parts.append(f"  地点：{location}")
    parts.append(f"  提前 {remind_before_min} 分钟提醒")

    return {"success": True, "id": event_id, "message": "\n".join(parts)}


async def list_events(group_platform_id: str | None = None, days: int = 7) -> dict:
    """查看近期日程（默认未来 7 天）。"""
    now = datetime.utcnow()
    end = now + timedelta(days=days)

    with db_session() as db:
        query = (
            select(CalendarEvent)
            .where(CalendarEvent.event_time >= now, CalendarEvent.event_time <= end)
            .order_by(CalendarEvent.event_time)
        )
        if group_platform_id:
            query = query.where(CalendarEvent.group_platform_id == group_platform_id)
        events = db.execute(query).scalars().all()

    if not events:
        return {"success": True, "events": [], "message": f"未来 {days} 天没有日程安排"}

    lines = [f"📅 未来 {days} 天日程："]
    for e in events:
        time_str = e.event_time.strftime("%m-%d %H:%M")
        loc = f" @ {e.location}" if e.location else ""
        lines.append(f"  #{e.id} {time_str} {e.title}{loc}")

    return {
        "success": True,
        "events": [{"id": e.id, "title": e.title, "time": e.event_time.isoformat()} for e in events],
        "message": "\n".join(lines),
    }


async def delete_event(event_id: int, operator_platform_id: str) -> dict:
    """删除日程。"""
    with db_session() as db:
        event = db.get(CalendarEvent, event_id)
        if not event:
            return {"success": False, "message": f"日程 #{event_id} 不存在"}
        db.delete(event)

    return {"success": True, "message": f"日程 #{event_id} 已删除"}


async def get_upcoming_reminders() -> list[dict]:
    """获取需要提醒的事件（供调度器调用）。"""
    now = datetime.utcnow()
    with db_session() as db:
        events = db.execute(
            select(CalendarEvent).where(
                CalendarEvent.reminded == False,
                CalendarEvent.event_time <= now + timedelta(minutes=60),
            )
        ).scalars().all()

    reminders = []
    for e in events:
        remind_at = e.event_time - timedelta(minutes=e.remind_before_min)
        if now >= remind_at:
            reminders.append({
                "id": e.id,
                "title": e.title,
                "event_time": e.event_time.isoformat(),
                "group_platform_id": e.group_platform_id,
                "creator_platform_id": e.creator_platform_id,
            })
            e.reminded = True

    if reminders:
        with db_session() as db:
            db.commit()

    return reminders
