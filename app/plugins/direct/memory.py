from __future__ import annotations

from app.ai.memory_manager import MemoryManager

_memory = MemoryManager()


async def remember_fact(content: str, scope_type: str = "user", scope_id: str = "") -> dict:
    """写入长期记忆。"""
    _memory.remember(scope_type=scope_type, scope_id=scope_id, content=content)
    return {
        "content": content,
        "scope_type": scope_type,
        "scope_id": scope_id,
        "message": f"已记住：{content}",
    }


async def recall_memory(query: str, scope_type: str = "user", scope_id: str = "") -> dict:
    """检索长期记忆。"""
    results = _memory.recall(scope_type=scope_type, scope_id=scope_id, query=query)
    return {
        "query": query,
        "results": results,
        "message": f"找到 {len(results)} 条相关记忆。" if results else "没有找到相关记忆。",
    }
