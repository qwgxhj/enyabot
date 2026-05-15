from pydantic import BaseModel
from typing import Any


class ToolResult(BaseModel):
    success: bool
    tool: str
    data: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
