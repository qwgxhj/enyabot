"""兼容层：旧的 app.tools 已迁移到 app.plugins。"""

from app.plugins import ToolRegistry, ToolSpec, register_builtin_tools

__all__ = ["ToolRegistry", "ToolSpec", "register_builtin_tools"]
