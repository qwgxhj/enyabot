from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass(slots=True)
class Persona:
    name: str
    style: str
    identity: str
    rules: list[str]
    forbidden: list[str]


class PersonaConfigLoader:
    def __init__(self, persona_dir: Path):
        self.persona_dir = persona_dir

    def load(self, persona_name: str) -> Persona:
        path = self.persona_dir / f"{persona_name}.yaml"
        if not path.exists():
            path = self.persona_dir / "default.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return Persona(
            name=data.get("name", "默认助理"),
            style=data.get("style", "自然简洁"),
            identity=data.get("identity", "社群智能助理"),
            rules=data.get("rules", []),
            forbidden=data.get("forbidden", []),
        )
