from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from loguru import logger


class ConfigManager:
    """Singleton config manager — reads config.yaml once, caches in memory."""

    _instance: ConfigManager | None = None
    _data: dict[str, Any]

    def __new__(cls) -> ConfigManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._data = {}
            cls._instance._loaded = False
        return cls._instance

    def load(self, path: str | Path) -> dict[str, Any]:
        p = Path(path)
        if not p.exists():
            logger.warning(f"ConfigManager: {p} not found, using empty config")
            self._data = {}
            self._loaded = True
            return self._data
        try:
            self._data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            self._loaded = True
        except Exception as exc:
            logger.warning(f"ConfigManager: failed to load {p}: {exc}")
            self._data = {}
        return self._data

    def get(self) -> dict[str, Any]:
        if not self._loaded:
            raise RuntimeError("ConfigManager not loaded yet — call load() first")
        return self._data

    def reload(self, path: str | Path) -> dict[str, Any]:
        """Force re-read from disk (useful after WebUI saves)."""
        self._loaded = False
        return self.load(path)
