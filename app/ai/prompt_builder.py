from datetime import datetime
from app.config.persona_config import Persona


class PromptBuilder:
    def build_system_prompt(self, persona: Persona, scene_text: str = "") -> str:
        rules = "\n".join(f"- {x}" for x in persona.rules)
        forbidden = "\n".join(f"- {x}" for x in persona.forbidden)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return (
            f"你是{persona.name}。身份：{persona.identity}。风格：{persona.style}。\n"
            f"当前时间：{now}\n"
            f"规则：\n{rules}\n"
            f"禁止事项：\n{forbidden}\n"
            f"场景信息：\n{scene_text}\n"
            "如果你调用工具，不要谎称工具已执行；必须根据工具结果回答。"
        )
