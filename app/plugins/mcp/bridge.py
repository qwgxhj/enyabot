from __future__ import annotations

import asyncio
from pathlib import Path

from loguru import logger

from app.plugins.base import ToolRegistry
from app.plugins.mcp.errors import MCPError
from app.plugins.mcp.loader import build_mcp_client, load_mcp_server_configs
from app.plugins.mcp.tool_adapter import mcp_tool_to_tool_spec


class MCPPluginBridge:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.clients: dict[str, object] = {}
        self.loaded_servers: list[str] = []

    @classmethod
    def from_base_dir(cls, base_dir: Path) -> "MCPPluginBridge":
        return cls(base_dir)

    async def register_tools(self, registry: ToolRegistry) -> int:
        config_path = self.base_dir / "config.yaml"
        server_configs = load_mcp_server_configs(config_path)
        if not server_configs:
            logger.info("MCP disabled or no servers configured")
            return 0

        registered = 0
        for server_config in server_configs:
            try:
                client = build_mcp_client(server_config)
                await client.connect()
                self.clients[server_config.name] = client
                tools = await asyncio.wait_for(client.list_tools(), timeout=server_config.timeout_seconds)
                count = 0
                for tool in tools:
                    if not server_config.should_enable_tool(tool.name):
                        continue
                    registry.register(mcp_tool_to_tool_spec(server_config, client, tool))
                    count += 1
                self.loaded_servers.append(server_config.name)
                registered += count
                logger.info("MCP server loaded: {} ({} tools)", server_config.name, count)
            except MCPError as exc:
                logger.warning("MCP server skipped: {} ({})", server_config.name, exc)
            except asyncio.TimeoutError:
                logger.warning("MCP server skipped: {} (list_tools timeout)", server_config.name)
            except Exception as exc:
                logger.exception("MCP server load failed: {} error={}", server_config.name, exc)
        return registered

    async def close(self) -> None:
        for name, client in list(self.clients.items()):
            try:
                await client.close()
            except Exception as exc:
                logger.warning("MCP client close failed: {} ({})", name, exc)
        self.clients.clear()
        self.loaded_servers.clear()

    def list_servers(self) -> list[str]:
        return list(self.loaded_servers)
