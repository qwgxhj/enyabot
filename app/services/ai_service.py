from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx

from app.ai.client import AIClient
from app.ai.memory_manager import MemoryManager
from app.ai.persona_manager import PersonaManager
from app.ai.prompt_builder import PromptBuilder
from app.ai.response_guard import ResponseGuard
from app.ai.tool_agent import ToolAgent
from app.config.config_manager import ConfigManager
from app.config.model_config import ModelConfig
from app.config.settings import env_settings
from app.core.context import ContextManager
from app.plugins.base import ToolRegistry


class AIService:
    def __init__(self, base_dir: Path, registry: ToolRegistry):
        self.base_dir = base_dir
        self.registry = registry
        self.client = AIClient()
        self.personas = PersonaManager(base_dir / "personas")
        self.prompt_builder = PromptBuilder()
        self.memory = MemoryManager()
        self.guard = ResponseGuard()
        self.context = ContextManager(max_rounds=12)
        self.app_config = ConfigManager().get()

    def _default_model(self) -> ModelConfig:
        return ModelConfig(
            provider_name="default",
            base_url=env_settings.openai_base_url,
            api_key=env_settings.openai_api_key,
            model_name=env_settings.default_model,
            timeout_seconds=60,
            max_tokens=1024,
            temperature=0.7,
            enabled=True,
            is_default=True,
        )

    def should_trigger_ai(self, event) -> bool:
        prefixes = self.app_config.get("ai", {}).get("trigger_prefixes", [])
        if event.event_type == "private_message":
            return True
        if event.is_at_bot:
            return True
        return any(event.raw_text.lower().startswith(str(prefix).lower()) for prefix in prefixes)

    def _extract_text_tool_calls(self, content: str) -> list[dict[str, Any]]:
        if not content:
            return []
        blocks = re.findall(r"<tool_call>\s*(.*?)\s*</tool_call>", content, flags=re.IGNORECASE | re.DOTALL)
        tool_calls: list[dict[str, Any]] = []
        for idx, block in enumerate(blocks, start=1):
            fn_match = re.search(r"<function\s*=\s*([^>\n]+)>", block, flags=re.IGNORECASE)
            end_fn_match = re.search(r"</function>", block, flags=re.IGNORECASE)
            if not fn_match or not end_fn_match:
                continue
            name = fn_match.group(1).strip()
            inner = block[fn_match.end():end_fn_match.start()]
            params: dict[str, Any] = {}
            for param_name, raw_value in re.findall(
                r"<parameter\s*=\s*([^>\n]+)>(.*?)</parameter>",
                inner,
                flags=re.IGNORECASE | re.DOTALL,
            ):
                key = param_name.strip()
                value_text = raw_value.strip()
                if not key:
                    continue
                try:
                    params[key] = json.loads(value_text)
                except Exception:
                    params[key] = value_text
            tool_calls.append(
                {
                    "id": f"text-tool-call-{idx}",
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(params, ensure_ascii=False),
                    },
                }
            )
        return tool_calls

    def _strip_text_tool_calls(self, content: str) -> str:
        if not content:
            return ""
        return re.sub(r"<tool_call>\s*.*?\s*</tool_call>", "", content, flags=re.IGNORECASE | re.DOTALL).strip()

    async def _run_tool_calls(self, messages: list[dict[str, Any]], tool_calls: list[dict[str, Any]], sender_role: str):
        tool_agent = ToolAgent(self.registry)
        assistant_message = {
            "role": "assistant",
            "content": None,
            "tool_calls": tool_calls,
        }
        messages.append(assistant_message)
        for tool_call in tool_calls:
            fn = (tool_call.get("function") or {})
            tool_name = fn.get("name", "")
            tool_result = await tool_agent.execute(tool_name, fn.get("arguments", "{}"), sender_role)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.get("id"),
                    "name": tool_name,
                    "content": tool_result.model_dump_json(ensure_ascii=False),
                }
            )

    async def chat(self, event) -> str:
        persona = self.personas.get(self.app_config.get("ai", {}).get("default_persona", "gentle_assistant"))
        scope_type = "group" if event.group_id else "private"
        scope_id = event.group_id or event.user_id
        session_key = self.context.build_session_key(scope_type, scope_id, event.user_id if scope_type == "group" else None)
        memories = self.memory.recall(scope_type, scope_id)

        # ── 图片识别：将图片转为文字描述 ──
        image_text = ""
        has_images = any(att.get("type") == "image" for att in (event.attachments or []))
        if has_images:
            from app.services.vision_service import extract_image_text
            image_text = await extract_image_text(event)

        # 构造用户消息（含图片描述）
        user_message = event.raw_text
        if image_text:
            user_message = f"{user_message}\n\n{image_text}" if user_message else image_text

        scene_text = f"scope_type={scope_type}; scope_id={scope_id}; memories={memories}"
        system_prompt = self.prompt_builder.build_system_prompt(persona, scene_text)

        self.context.append(session_key, "user", user_message)
        messages = [{"role": "system", "content": system_prompt}, *self.context.get(session_key)]
        model = self._default_model()
        tools = self.registry.all_openai_schemas()

        if not model.api_key:
            text = "AI 已触发，但当前未配置 OPENAI_API_KEY；请先在 .env 中填写。"
            self.context.append(session_key, "assistant", text)
            return text

        try:
            content = ""
            for _ in range(4):
                result = await self.client.chat(messages=messages, model_config=model, tools=tools)
                choice = ((result.get("choices") or [{}])[0]).get("message", {})
                tool_calls = choice.get("tool_calls") or []
                content = choice.get("content") or ""
                if not tool_calls:
                    tool_calls = self._extract_text_tool_calls(content)
                if tool_calls:
                    await self._run_tool_calls(messages, tool_calls, event.sender_role)
                    content = ""
                    continue
                content = self._strip_text_tool_calls(content)
                if content:
                    break

            if not content:
                result = await self.client.chat(messages=messages, model_config=model, tools=None)
                choice = ((result.get("choices") or [{}])[0]).get("message", {})
                content = self._strip_text_tool_calls(choice.get("content") or "")

            text = self.guard.review(content or "我拿到了工具调用过程，但模型没有生成最终答复。请重试一次，或换一个更支持工具调用的模型。")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                text = "AI 接口鉴权失败（401）。请检查 .env 里的 OPENAI_API_KEY 和 OPENAI_BASE_URL 是否正确。"
            else:
                text = f"AI 接口调用失败（HTTP {exc.response.status_code}）。请检查模型名、接口地址或服务状态。"
        except Exception:
            text = "AI 暂时不可用，请稍后再试。"

        self.context.append(session_key, "assistant", text)
        return text
