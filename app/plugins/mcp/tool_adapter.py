from __future__ import annotations

from app.plugins.base import ToolSpec
from app.plugins.mcp.base import BaseMCPClient
from app.plugins.mcp.models import MCPServerConfig, MCPToolDescriptor


def _normalize_schema(schema: dict | None) -> dict:
    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}}
    if "type" not in schema:
        schema = {"type": "object", **schema}
    schema.setdefault("properties", {})
    return schema


def mcp_tool_to_tool_spec(config: MCPServerConfig, client: BaseMCPClient, tool: MCPToolDescriptor) -> ToolSpec:
    final_name = config.final_tool_name(tool.name)
    schema = _normalize_schema(tool.input_schema)
    description = (tool.description or "MCP 工具").strip()

    async def _handler(**kwargs):
        return await client.call_tool(tool.name, kwargs)

    return ToolSpec(
        name=final_name,
        description=description,
        input_schema=schema,
        permission_level=config.default_permission,
        handler=_handler,
        enabled=True,
        category="mcp",
        source=config.source,
    )
