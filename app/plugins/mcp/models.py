from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def normalize_tool_segment(value: str) -> str:
    cleaned = (value or "").strip().replace("-", "_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_")


@dataclass(slots=True)
class MCPServerConfig:
    name: str
    transport: str = "stdio"
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str | None = None
    enabled: bool = True
    timeout_seconds: int = 20
    default_permission: str = "member"
    enabled_tools: list[str] = field(default_factory=list)
    disabled_tools: list[str] = field(default_factory=list)
    tool_prefix: str | None = None

    @property
    def source(self) -> str:
        return f"mcp:{self.name}"

    def should_enable_tool(self, tool_name: str) -> bool:
        if self.enabled_tools and tool_name not in self.enabled_tools:
            return False
        if tool_name in self.disabled_tools:
            return False
        return True

    def final_tool_name(self, tool_name: str) -> str:
        prefix = normalize_tool_segment(self.tool_prefix or self.name)
        tool_name = normalize_tool_segment(tool_name)
        if not prefix:
            return tool_name
        return f"{prefix}__{tool_name}"


@dataclass(slots=True)
class MCPToolDescriptor:
    name: str
    description: str
    input_schema: dict[str, Any]
    raw: Any = None
