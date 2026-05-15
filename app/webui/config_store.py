from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from app.config.settings import env_settings
from app.host import HOST


BASE_DIR = Path(__file__).resolve().parents[2]
PERSONA_DIR = BASE_DIR / "personas"
CONFIG_PATH = BASE_DIR / "config.yaml"
ENV_PATH = BASE_DIR / ".env"
_VALID_BOOL_VALUES = {"true", "false"}
_VALID_MCP_TRANSPORTS = {"stdio", "http", "sse"}
_PERSONA_FILE_RE = re.compile(r"[^A-Za-z0-9_-]+")


def _sync_env_to_runtime(values: dict[str, str]) -> None:
    """将写入 .env 的值同步到 os.environ 和 env_settings 单例。"""
    _ENV_KEY_MAP = {
        "OPENAI_API_KEY": "openai_api_key",
        "OPENAI_BASE_URL": "openai_base_url",
        "DEFAULT_MODEL": "default_model",
        "APP_ENV": "app_env",
        "APP_DEBUG": "app_debug",
        "DATABASE_URL": "database_url",
    }
    for env_key, new_val in values.items():
        os.environ[env_key] = new_val
        attr = _ENV_KEY_MAP.get(env_key)
        if attr and hasattr(env_settings, attr):
            try:
                object.__setattr__(env_settings, attr, new_val)
            except Exception:
                pass


class ConfigValidationError(ValueError):
    pass


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = path.with_suffix(path.suffix + ".bak")
    temp_path = path.with_suffix(path.suffix + ".tmp")

    if path.exists():
        backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    temp_path.write_text(content, encoding="utf-8")
    os.replace(temp_path, path)


def read_yaml_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def write_yaml_config(data: dict[str, Any]) -> None:
    _atomic_write_text(
        CONFIG_PATH,
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
    )


def read_env_file() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_PATH.exists():
        return values
    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def write_env_file(values: dict[str, str]) -> None:
    existing_lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    pending = dict(values)
    rendered: list[str] = []

    for raw_line in existing_lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in raw_line:
            rendered.append(raw_line)
            continue
        key, _ = raw_line.split("=", 1)
        clean_key = key.strip()
        if clean_key in pending:
            rendered.append(f"{clean_key}={pending.pop(clean_key)}")
        else:
            rendered.append(raw_line)

    for key, value in pending.items():
        rendered.append(f"{key}={value}")

    _atomic_write_text(ENV_PATH, "\n".join(rendered).rstrip() + "\n")

    # 同步更新进程环境变量和 env_settings 单例，确保重启 bot 后立即生效
    _sync_env_to_runtime(values)


def list_personas() -> list[str]:
    if not PERSONA_DIR.exists():
        return []
    return sorted(path.stem for path in PERSONA_DIR.glob("*.yaml"))


def load_persona(persona_name: str) -> dict[str, Any]:
    path = PERSONA_DIR / f"{persona_name}.yaml"
    if not path.exists():
        path = PERSONA_DIR / "default.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        "file_name": path.stem,
        "name": data.get("name", ""),
        "style": data.get("style", ""),
        "identity": data.get("identity", ""),
        "rules": data.get("rules", []),
        "forbidden": data.get("forbidden", []),
    }


def _sanitize_persona_file_name(persona_file_name: str) -> str:
    raw = (persona_file_name or "default").strip().replace(" ", "_")
    safe_name = _PERSONA_FILE_RE.sub("_", raw).strip("._-")
    if not safe_name:
        raise ConfigValidationError("人设文件名不能为空，且只能包含字母、数字、下划线或短横线。")
    return safe_name


def save_persona(persona_file_name: str, payload: dict[str, Any]) -> str:
    PERSONA_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = _sanitize_persona_file_name(persona_file_name)
    path = PERSONA_DIR / f"{safe_name}.yaml"
    data = {
        "name": (payload.get("name", safe_name) or safe_name).strip(),
        "style": payload.get("style", ""),
        "identity": payload.get("identity", ""),
        "rules": payload.get("rules", []),
        "forbidden": payload.get("forbidden", []),
    }
    _atomic_write_text(path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
    return safe_name


def _normalize_mcp_server(server: dict[str, Any], index: int) -> dict[str, Any]:
    args = server.get("args", [])
    enabled_tools = server.get("enabled_tools", [])
    disabled_tools = server.get("disabled_tools", [])
    return {
        "index": index,
        "name": server.get("name", f"server_{index + 1}"),
        "transport": server.get("transport", "stdio"),
        "command": server.get("command", ""),
        "args": args if isinstance(args, list) else [],
        "default_permission": server.get("default_permission", "member"),
        "tool_prefix": server.get("tool_prefix", ""),
        "timeout_seconds": server.get("timeout_seconds", 30),
        "enabled_tools": enabled_tools if isinstance(enabled_tools, list) else [],
        "disabled_tools": disabled_tools if isinstance(disabled_tools, list) else [],
    }


def list_mcp_servers(config: dict[str, Any]) -> list[dict[str, Any]]:
    mcp_cfg = config.get("mcp", {}) if isinstance(config.get("mcp", {}), dict) else {}
    servers = mcp_cfg.get("servers", [])
    if not isinstance(servers, list):
        servers = []
    items = [_normalize_mcp_server(item or {}, idx) for idx, item in enumerate(servers)]
    if not items:
        items.append(_normalize_mcp_server({}, 0))
    return items


def get_dashboard_state(selected_persona: str | None = None) -> dict[str, Any]:
    config = read_yaml_config()
    env = read_env_file()
    personas = list_personas()
    active_persona = selected_persona or config.get("ai", {}).get("default_persona", "default")
    if active_persona not in personas and personas:
        active_persona = personas[0]

    ai_cfg = config.setdefault("ai", {})
    napcat_cfg = config.setdefault("napcat", {})
    features_cfg = config.setdefault("features", {})
    mcp_cfg = config.setdefault("mcp", {})
    host_status = HOST.get_status()

    return {
        "config": config,
        "env": env,
        "personas": personas,
        "selected_persona": active_persona,
        "persona": load_persona(active_persona or "default"),
        "mcp_servers": list_mcp_servers(config),
        "runtime": {
            "bot_running": host_status.running,
            "webui_running": host_status.webui_running,
            "ws_url": host_status.ws_url,
        },
        "form": {
            "openai_base_url": env.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            "openai_api_key": env.get("OPENAI_API_KEY", ""),
            "default_model": env.get("DEFAULT_MODEL", "gpt-4o-mini"),
            "app_env": env.get("APP_ENV", config.get("app", {}).get("env", "dev")),
            "ws_url": napcat_cfg.get("ws_url", "ws://127.0.0.1:3001"),
            "default_persona": ai_cfg.get("default_persona", "default"),
            "max_context_rounds": ai_cfg.get("max_context_rounds", 12),
            "tool_call_enabled": ai_cfg.get("tool_call_enabled", True),
            "memory_enabled": ai_cfg.get("memory_enabled", True),
            "trigger_prefixes": "\n".join(ai_cfg.get("trigger_prefixes", [])),
            "feature_ai": features_cfg.get("ai", True),
            "mcp_enabled": mcp_cfg.get("enabled", False),
            "master_qq": str(config.get("bot", {}).get("master_qq", "")),
            "master2_qq": "|".join(config.get("bot", {}).get("master2_qq", [])) if isinstance(config.get("bot", {}).get("master2_qq"), list) else str(config.get("bot", {}).get("master2_qq", "")),
        },
    }


def _parse_bool_field(name: str, raw: str, default: bool = False) -> bool:
    value = (raw or "").strip().lower()
    if not value:
        return default
    if value not in _VALID_BOOL_VALUES:
        raise ConfigValidationError(f"字段 {name} 只能是 true 或 false。")
    return value == "true"


def _parse_positive_int(name: str, raw: str, default: int, minimum: int = 1) -> int:
    value = (raw or "").strip() or str(default)
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConfigValidationError(f"字段 {name} 必须是整数。") from exc
    if parsed < minimum:
        raise ConfigValidationError(f"字段 {name} 不能小于 {minimum}。")
    return parsed


def _require_text(name: str, raw: str, default: str = "") -> str:
    value = (raw or default).strip()
    if not value:
        raise ConfigValidationError(f"字段 {name} 不能为空。")
    return value


def _parse_list_field(raw: str) -> list[str]:
    return [line.strip() for line in raw.splitlines() if line.strip()]


def update_settings_from_form(form: dict[str, str]) -> None:
    config = read_yaml_config()
    env = read_env_file()

    app_env = _require_text("APP_ENV", form.get("app_env", "dev"), "dev")
    ws_url = _require_text("NapCat WebSocket 地址", form.get("ws_url", "ws://127.0.0.1:3001"), "ws://127.0.0.1:3001")
    openai_base_url = _require_text("OPENAI_BASE_URL", form.get("openai_base_url", "https://api.openai.com/v1"), "https://api.openai.com/v1")
    default_model = _require_text("DEFAULT_MODEL", form.get("default_model", "gpt-4o-mini"), "gpt-4o-mini")
    default_persona = _sanitize_persona_file_name(form.get("default_persona", "default") or "default")
    max_context_rounds = _parse_positive_int("max_context_rounds", form.get("max_context_rounds", "12"), 12)
    tool_call_enabled = _parse_bool_field("tool_call_enabled", form.get("tool_call_enabled", "false"))
    memory_enabled = _parse_bool_field("memory_enabled", form.get("memory_enabled", "false"))
    feature_ai = _parse_bool_field("feature_ai", form.get("feature_ai", "false"))
    mcp_enabled = _parse_bool_field("mcp_enabled", form.get("mcp_enabled", "false"))
    trigger_prefixes = _parse_list_field(form.get("trigger_prefixes", ""))

    config.setdefault("app", {})["env"] = app_env
    config.setdefault("napcat", {})["ws_url"] = ws_url

    ai_cfg = config.setdefault("ai", {})
    ai_cfg["default_persona"] = default_persona
    ai_cfg["max_context_rounds"] = max_context_rounds
    ai_cfg["tool_call_enabled"] = tool_call_enabled
    ai_cfg["memory_enabled"] = memory_enabled
    ai_cfg["trigger_prefixes"] = trigger_prefixes

    config.setdefault("features", {})["ai"] = feature_ai
    config.setdefault("mcp", {})["enabled"] = mcp_enabled

    env["APP_ENV"] = app_env
    env["OPENAI_BASE_URL"] = openai_base_url
    if form.get("openai_api_key", "").strip():
        env["OPENAI_API_KEY"] = form.get("openai_api_key", "").strip()
    env["DEFAULT_MODEL"] = default_model

    # 主人配置
    bot_cfg = config.setdefault("bot", {})
    master_qq = form.get("master_qq", "").strip()
    master2_qq = form.get("master2_qq", "").strip()
    if master_qq:
        bot_cfg["master_qq"] = master_qq
    elif "master_qq" not in bot_cfg:
        bot_cfg["master_qq"] = ""
    if master2_qq:
        bot_cfg["master2_qq"] = [x.strip() for x in master2_qq.split("|") if x.strip()]
    elif "master2_qq" not in bot_cfg:
        bot_cfg["master2_qq"] = []

    write_yaml_config(config)
    write_env_file(env)


def update_mcp_servers_from_form(form: dict[str, str]) -> None:
    config = read_yaml_config()
    mcp_cfg = config.setdefault("mcp", {})

    count = _parse_positive_int("server_count", form.get("server_count", "1"), 1)
    servers: list[dict[str, Any]] = []
    for idx in range(count):
        prefix = f"server_{idx}_"
        name = form.get(prefix + "name", "").strip()
        command = form.get(prefix + "command", "").strip()
        transport = (form.get(prefix + "transport", "stdio") or "stdio").strip().lower()
        tool_prefix = form.get(prefix + "tool_prefix", "").strip()
        default_permission = form.get(prefix + "default_permission", "member").strip() or "member"
        timeout_seconds = _parse_positive_int(
            f"server_{idx + 1}.timeout_seconds",
            form.get(prefix + "timeout_seconds", "30"),
            30,
        )
        args = _parse_list_field(form.get(prefix + "args", ""))
        enabled_tools = _parse_list_field(form.get(prefix + "enabled_tools", ""))
        disabled_tools = _parse_list_field(form.get(prefix + "disabled_tools", ""))

        if not name and not command and not args and not tool_prefix:
            continue

        if transport not in _VALID_MCP_TRANSPORTS:
            raise ConfigValidationError(f"server_{idx + 1}.transport 只能是 stdio、http 或 sse。")
        if not default_permission:
            raise ConfigValidationError(f"server_{idx + 1}.default_permission 不能为空。")
        if transport == "stdio" and not command:
            raise ConfigValidationError(f"server_{idx + 1} 使用 stdio 时必须填写 command。")

        server: dict[str, Any] = {
            "name": name or f"server_{idx + 1}",
            "transport": transport,
            "default_permission": default_permission,
            "tool_prefix": tool_prefix,
            "timeout_seconds": timeout_seconds,
        }
        if command:
            server["command"] = command
        if args:
            server["args"] = args
        if enabled_tools:
            server["enabled_tools"] = enabled_tools
        if disabled_tools:
            server["disabled_tools"] = disabled_tools
        servers.append(server)

    mcp_cfg["servers"] = servers
    write_yaml_config(config)


def update_persona_from_form(form: dict[str, str]) -> str:
    persona_file_name = form.get("persona_file_name", "") or "default"
    rules = [line.strip() for line in form.get("rules", "").splitlines() if line.strip()]
    forbidden = [line.strip() for line in form.get("forbidden", "").splitlines() if line.strip()]
    return save_persona(
        persona_file_name,
        {
            "name": (form.get("name", persona_file_name) or persona_file_name).strip() or "default",
            "style": form.get("style", "").strip(),
            "identity": form.get("identity", "").strip(),
            "rules": rules,
            "forbidden": forbidden,
        },
    )
