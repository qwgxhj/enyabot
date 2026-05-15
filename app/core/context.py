from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from loguru import logger


_DEFAULT_PERSIST_PATH = Path("data/context_sessions.json")


class ContextManager:
    def __init__(self, max_rounds: int = 12, persist_path: str | Path | None = None):
        self.max_rounds = max_rounds
        self._persist_path = Path(persist_path) if persist_path else _DEFAULT_PERSIST_PATH
        self.sessions: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._load()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._persist_path.exists():
            return
        try:
            raw = json.loads(self._persist_path.read_text(encoding="utf-8"))
            for key, msgs in raw.items():
                self.sessions[key] = msgs[-self.max_rounds * 2 :]
            logger.info(f"ContextManager loaded {len(self.sessions)} sessions from {self._persist_path}")
        except Exception as exc:
            logger.warning(f"ContextManager load failed, starting fresh: {exc}")

    def _save(self) -> None:
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._persist_path.write_text(
                json.dumps(dict(self.sessions), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning(f"ContextManager save failed: {exc}")

    # ------------------------------------------------------------------
    # Public API (unchanged signatures)
    # ------------------------------------------------------------------

    def build_session_key(self, scope_type: str, scope_id: str, user_id: str | None = None) -> str:
        return f"{scope_type}:{scope_id}:{user_id or ''}"

    def append(self, session_key: str, role: str, content: str):
        self.sessions[session_key].append({"role": role, "content": content})
        self.sessions[session_key] = self.sessions[session_key][-self.max_rounds * 2 :]
        self._save()

    def get(self, session_key: str) -> list[dict[str, Any]]:
        return list(self.sessions.get(session_key, []))
