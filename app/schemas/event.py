from pydantic import BaseModel, Field
from typing import Any


class Event(BaseModel):
    event_id: str
    event_type: str
    time: int
    platform: str = "qq"
    self_id: str | None = None
    group_id: str | None = None
    user_id: str
    message_id: str | None = None
    raw_text: str = ""
    is_at_bot: bool = False
    mentions: list[str] = Field(default_factory=list)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    sender_role: str = "member"
    raw_payload: dict[str, Any] = Field(default_factory=dict)
