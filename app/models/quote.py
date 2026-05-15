"""语录 / 名言数据模型。"""
from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.db.base import Base


class Quote(Base):
    """群语录。"""
    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_platform_id: Mapped[str] = mapped_column(String(64), index=True)
    content: Mapped[str] = mapped_column(Text)
    author_platform_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    author_nickname: Mapped[str | None] = mapped_column(String(128), nullable=True)
    added_by_platform_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
