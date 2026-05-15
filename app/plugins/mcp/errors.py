from __future__ import annotations

class MCPError(Exception):
    """MCP 基础异常。"""


class MCPConfigError(MCPError):
    """MCP 配置异常。"""


class MCPClientUnavailableError(MCPError):
    """MCP 客户端依赖不可用。"""


class MCPTransportNotSupportedError(MCPError):
    """当前版本暂不支持该 transport。"""
