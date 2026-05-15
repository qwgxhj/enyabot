"""消息日志服务 — 记录所有 NapCat 收发消息，供 WebUI 查看。"""
from __future__ import annotations

import json
import time
from collections import deque
from pathlib import Path
from typing import Any

from loguru import logger

# 内存中保留最近 2000 条消息
_messages: deque[dict[str, Any]] = deque(maxlen=2000)
_log_path: Path | None = None


def init(base_dir: Path) -> None:
    global _log_path
    log_dir = base_dir / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    _log_path = log_dir / "messages.jsonl"


def log_incoming(event_type: str, group_id: str, user_id: str, content: str, raw: dict | None = None) -> None:
    """记录收到的消息。"""
    entry = {
        "time": time.time(),
        "time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "direction": "in",
        "type": event_type,
        "group_id": group_id or "",
        "user_id": user_id or "",
        "content": _truncate(content, 500),
    }
    _append(entry)


def log_outgoing(action: str, group_id: str, user_id: str, content: str, success: bool = True) -> None:
    """记录发送的消息。"""
    entry = {
        "time": time.time(),
        "time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "direction": "out",
        "type": action,
        "group_id": group_id or "",
        "user_id": user_id or "",
        "content": _truncate(content, 500),
        "success": success,
    }
    _append(entry)


def log_system(event: str, detail: str = "") -> None:
    """记录系统事件。"""
    entry = {
        "time": time.time(),
        "time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "direction": "system",
        "type": event,
        "group_id": "",
        "user_id": "",
        "content": _truncate(detail, 500),
    }
    _append(entry)


def _truncate(text: str, max_len: int) -> str:
    if not text:
        return ""
    text = str(text).replace("\n", " ").strip()
    return text[:max_len] + "..." if len(text) > max_len else text


def _append(entry: dict) -> None:
    _messages.append(entry)
    if _log_path:
        try:
            with open(_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass


def get_messages(limit: int = 200, direction: str = "", group_id: str = "", search: str = "") -> list[dict]:
    """获取消息列表，支持过滤。"""
    msgs = list(_messages)
    if direction:
        msgs = [m for m in msgs if m.get("direction") == direction]
    if group_id:
        msgs = [m for m in msgs if group_id in m.get("group_id", "")]
    if search:
        search_lower = search.lower()
        msgs = [m for m in msgs if search_lower in m.get("content", "").lower() or search_lower in m.get("user_id", "")]
    return msgs[-limit:]


def get_stats() -> dict:
    """获取消息统计。"""
    msgs = list(_messages)
    return {
        "total": len(msgs),
        "incoming": sum(1 for m in msgs if m.get("direction") == "in"),
        "outgoing": sum(1 for m in msgs if m.get("direction") == "out"),
        "system": sum(1 for m in msgs if m.get("direction") == "system"),
    }
