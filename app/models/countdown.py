"""倒数日 / 纪念日数据模型。"""
from sqlalchemy import String, Boolean, DateTime, Date
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, date

from app.db.base import Base


class Countdown(Base):
    """倒数日。"""
    __tablename__ = "countdowns"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_platform_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    creator_platform_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128))
    target_date: Mapped[date] = mapped_column(Date, index=True)
    remind_daily: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
