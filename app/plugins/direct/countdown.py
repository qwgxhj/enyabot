"""倒数日 / 纪念日插件。"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select

from app.db.session import db_session
from app.models.countdown import Countdown


async def add_countdown(
    creator_platform_id: str,
    name: str,
    target_date_str: str,
    group_platform_id: str | None = None,
    remind_daily: bool = False,
) -> dict:
    """添加倒数日。target_date_str 格式：YYYY-MM-DD"""
    name = (name or "").strip()
    target_date_str = (target_date_str or "").strip()
    if not name:
        return {"success": False, "message": "名称不能为空"}
    if not target_date_str:
        return {"success": False, "message": "日期不能为空，格式：YYYY-MM-DD\n例如：2026-06-07"}

    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    except ValueError:
        return {"success": False, "message": "日期格式错误，正确格式：YYYY-MM-DD\n例如：2026-06-07"}

    today = date.today()
    days_left = (target_date - today).days

    with db_session() as db:
        cd = Countdown(
            group_platform_id=group_platform_id,
            creator_platform_id=creator_platform_id,
            name=name,
            target_date=target_date,
            remind_daily=remind_daily,
        )
        db.add(cd)
        db.flush()
        cd_id = cd.id

    if days_left > 0:
        msg = f"⏰ 倒数日已添加（#{cd_id}）\n  {name}：距离 {target_date_str} 还有 {days_left} 天"
    elif days_left == 0:
        msg = f"⏰ 倒数日已添加（#{cd_id}）\n  {name}：就是今天！🎉"
    else:
        msg = f"⏰ 倒数日已添加（#{cd_id}）\n  {name}：{target_date_str} 已过去 {abs(days_left)} 天"

    return {"success": True, "id": cd_id, "days_left": days_left, "message": msg}


async def list_countdowns(group_platform_id: str | None = None) -> dict:
    """列出倒数日。"""
    today = date.today()

    with db_session() as db:
        query = select(Countdown).order_by(Countdown.target_date)
        if group_platform_id:
            query = query.where(Countdown.group_platform_id == group_platform_id)
        countdowns = db.execute(query).scalars().all()

    if not countdowns:
        return {"success": True, "countdowns": [], "message": "当前没有倒数日"}

    lines = ["⏰ 倒数日列表："]
    for cd in countdowns:
        days_left = (cd.target_date - today).days
        if days_left > 0:
            status = f"还有 {days_left} 天"
        elif days_left == 0:
            status = "就是今天！🎉"
        else:
            status = f"已过去 {abs(days_left)} 天"
        lines.append(f"  #{cd.id} {cd.name}（{cd.target_date}）→ {status}")

    return {
        "success": True,
        "countdowns": [{"id": cd.id, "name": cd.name, "date": str(cd.target_date)} for cd in countdowns],
        "message": "\n".join(lines),
    }


async def delete_countdown(cd_id: int) -> dict:
    """删除倒数日。"""
    with db_session() as db:
        cd = db.get(Countdown, cd_id)
        if not cd:
            return {"success": False, "message": f"倒数日 #{cd_id} 不存在"}
        db.delete(cd)

    return {"success": True, "message": f"倒数日 #{cd_id} 已删除"}


async def get_daily_countdowns() -> list[dict]:
    """获取今日需要提醒的倒数日（供调度器调用）。"""
    today = date.today()
    with db_session() as db:
        countdowns = db.execute(
            select(Countdown).where(Countdown.remind_daily == True)
        ).scalars().all()

    results = []
    for cd in countdowns:
        days_left = (cd.target_date - today).days
        results.append({
            "id": cd.id,
            "name": cd.name,
            "target_date": str(cd.target_date),
            "days_left": days_left,
            "group_platform_id": cd.group_platform_id,
        })

    return results
