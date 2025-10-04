from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from loguru import logger

CONFIG_DIR = Path(__file__).parent
env_file_path = CONFIG_DIR / ".env"
env_file = str(env_file_path)

if env_file_path.exists():
    logger.warning(f"Using .env file at {env_file_path.resolve()} for configuration.")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=env_file, env_file_encoding="utf-8")

    openrouter_api_key: Optional[str] = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "moonshotai/kimi-vl-a3b-thinking:free"

    openai_key: Optional[str] = None
    openai_model: str = "moonshotai/kimi-vl-a3b-thinking:free"

    host: str = "localhost"
    port: int = 10000


settings = Settings()
