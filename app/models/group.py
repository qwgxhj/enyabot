from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.db.base import Base


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform_group_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    group_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    default_model_id: Mapped[int | None] = mapped_column(nullable=True)
    default_persona: Mapped[str] = mapped_column(String(64), default="gentle_assistant")
    welcome_text: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
