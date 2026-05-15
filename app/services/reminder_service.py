from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.group import Group
from app.models.reminder import Reminder
from app.models.user import User


class ReminderService:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()

    def create_reminder(self, user_platform_id: str, group_platform_id: str | None, content: str, minutes: int = 30) -> str:
        remind_at = datetime.utcnow() + timedelta(minutes=minutes)
        with SessionLocal() as db:
            user = db.execute(select(User).where(User.platform_user_id == user_platform_id)).scalar_one_or_none()
            if user is None:
                raise ValueError(f"未找到用户 {user_platform_id}")
            group = None
            if group_platform_id:
                group = db.execute(select(Group).where(Group.platform_group_id == group_platform_id)).scalar_one_or_none()
            reminder = Reminder(
                group_id=group.id if group else None,
                user_id=user.id,
                remind_at=remind_at,
                content=content,
                status="pending",
            )
            db.add(reminder)
            db.commit()
        return remind_at.strftime("%Y-%m-%d %H:%M:%S UTC")
