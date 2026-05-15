from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvSettings(BaseSettings):
    app_name: str = "qq-ai-bot"
    app_env: str = "dev"
    app_debug: bool = True
    database_url: str = "sqlite:///data/bot.db"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    default_model: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


env_settings = EnvSettings()
