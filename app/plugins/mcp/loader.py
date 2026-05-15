from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.plugins.mcp.errors import MCPConfigError, MCPTransportNotSupportedError
from app.plugins.mcp.models import MCPServerConfig
from app.plugins.mcp.client_stdio import StdioMCPClient


def load_mcp_server_configs(config_path: Path) -> list[MCPServerConfig]:
    if not config_path.exists():
        return []

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    mcp_block = raw.get("mcp") or {}
    if not isinstance(mcp_block, dict):
        raise MCPConfigError("config.yaml 中的 mcp 配置必须是对象")
    if not mcp_block.get("enabled", False):
        return []

    servers: list[MCPServerConfig] = []
    servers.extend(_load_project_servers(mcp_block.get("servers") or []))
    servers.extend(_load_standard_mcp_servers(mcp_block.get("mcpServers") or {}))
    return [server for server in servers if server.enabled]


def build_mcp_client(config: MCPServerConfig):
    transport = (config.transport or "stdio").lower()
    if transport == "stdio":
        if not config.command:
            raise MCPConfigError(f"MCP server `{config.name}` 缺少 command")
        return StdioMCPClient(config)
    raise MCPTransportNotSupportedError(f"当前 V1 仅支持 stdio，暂不支持 `{transport}`")


def _load_project_servers(items: list[Any]) -> list[MCPServerConfig]:
    servers: list[MCPServerConfig] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        servers.append(
            MCPServerConfig(
                name=name,
                transport=str(item.get("transport") or "stdio"),
                command=item.get("command"),
                args=[str(arg) for arg in (item.get("args") or [])],
                env={str(k): str(v) for k, v in (item.get("env") or {}).items()},
                url=item.get("url"),
                enabled=bool(item.get("enabled", True)),
                timeout_seconds=int(item.get("timeout_seconds") or 20),
                default_permission=str(item.get("default_permission") or "member"),
                enabled_tools=[str(x) for x in (item.get("enabled_tools") or [])],
                disabled_tools=[str(x) for x in (item.get("disabled_tools") or [])],
                tool_prefix=item.get("tool_prefix"),
            )
        )
    return servers


def _load_standard_mcp_servers(mapping: dict[str, Any]) -> list[MCPServerConfig]:
    servers: list[MCPServerConfig] = []
    if not isinstance(mapping, dict):
        return servers
    for name, item in mapping.items():
        if not isinstance(item, dict):
            continue
        servers.append(
            MCPServerConfig(
                name=str(name).strip(),
                transport=str(item.get("transport") or "stdio"),
                command=item.get("command"),
                args=[str(arg) for arg in (item.get("args") or [])],
                env={str(k): str(v) for k, v in (item.get("env") or {}).items()},
                url=item.get("url"),
                enabled=bool(item.get("enabled", True)),
                timeout_seconds=int(item.get("timeout_seconds") or 20),
                default_permission=str(item.get("default_permission") or "member"),
                enabled_tools=[str(x) for x in (item.get("enabled_tools") or [])],
                disabled_tools=[str(x) for x in (item.get("disabled_tools") or [])],
                tool_prefix=item.get("tool_prefix") or str(name).strip(),
            )
        )
    return servers
