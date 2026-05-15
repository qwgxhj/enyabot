"""增强版关键词数据模型（支持正则、随机回复、冷却时间）。"""
from sqlalchemy import String, Integer, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.db.base import Base


class KeywordRule(Base):
    """关键词规则。"""
    __tablename__ = "keyword_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_platform_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    pattern: Mapped[str] = mapped_column(Text)  # 关键词或正则
    is_regex: Mapped[bool] = mapped_column(Boolean, default=False)
    replies: Mapped[str] = mapped_column(Text)  # JSON: ["回复1", "回复2", ...]，随机选一条
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    creator_platform_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
