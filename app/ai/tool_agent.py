from __future__ import annotations

import json

from app.core.permissions import has_permission
from app.plugins.base import ToolRegistry
from app.plugins.mcp.models import normalize_tool_segment
from app.schemas.tool import ToolResult


class ToolAgent:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def _normalize_tool_name(self, tool_name: str) -> str:
        if "__" not in tool_name:
            return normalize_tool_segment(tool_name)
        prefix, name = tool_name.split("__", 1)
        return f"{normalize_tool_segment(prefix)}__{normalize_tool_segment(name)}"

    async def execute(self, tool_name: str, arguments: str | dict, sender_role: str) -> ToolResult:
        normalized_name = self._normalize_tool_name(tool_name)
        tool = self.registry.get(tool_name) or self.registry.get(normalized_name)
        final_name = tool.name if tool is not None else normalized_name
        if tool is None:
            return ToolResult(success=False, tool=final_name, error={"code": "TOOL_NOT_FOUND", "message": "工具不存在"})
        if not has_permission(sender_role, tool.permission_level):
            return ToolResult(success=False, tool=tool.name, error={"code": "PERMISSION_DENIED", "message": "权限不足"})
        if isinstance(arguments, str):
            arguments = json.loads(arguments or "{}")
        data = await tool.handler(**arguments)
        return ToolResult(success=True, tool=tool.name, data=data)
