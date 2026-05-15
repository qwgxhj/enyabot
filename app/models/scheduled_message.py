"""定时消息 / 周期性公告数据模型。"""
from sqlalchemy import String, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.db.base import Base


class ScheduledMessage(Base):
    """定时/周期消息。"""
    __tablename__ = "scheduled_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_platform_id: Mapped[str] = mapped_column(String(64), index=True)
    creator_platform_id: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text)
    cron_expr: Mapped[str] = mapped_column(String(128))  # cron 表达式
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
