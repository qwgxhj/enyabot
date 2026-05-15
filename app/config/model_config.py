from dataclasses import dataclass


@dataclass(slots=True)
class ModelConfig:
    provider_name: str
    base_url: str
    api_key: str
    model_name: str
    timeout_seconds: int = 60
    max_tokens: int = 1024
    temperature: float = 0.7
    enabled: bool = True
    is_default: bool = False
