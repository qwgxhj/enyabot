from pathlib import Path
from app.config.persona_config import PersonaConfigLoader, Persona


class PersonaManager:
    def __init__(self, persona_dir: Path):
        self.loader = PersonaConfigLoader(persona_dir)

    def get(self, persona_name: str) -> Persona:
        return self.loader.load(persona_name)
