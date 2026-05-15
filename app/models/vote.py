"""投票/问卷数据模型。"""
from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.db.base import Base


class Vote(Base):
    """投票主表。"""
    __tablename__ = "votes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_platform_id: Mapped[str] = mapped_column(String(64), index=True)
    creator_platform_id: Mapped[str] = mapped_column(String(64))
    question: Mapped[str] = mapped_column(Text)
    options: Mapped[str] = mapped_column(Text)  # JSON: ["选项A", "选项B", ...]
    anonymous: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open / closed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class VoteRecord(Base):
    """投票记录。"""
    __tablename__ = "vote_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    vote_id: Mapped[int] = mapped_column(ForeignKey("votes.id"), index=True)
    voter_platform_id: Mapped[str] = mapped_column(String(64))
    option_index: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
