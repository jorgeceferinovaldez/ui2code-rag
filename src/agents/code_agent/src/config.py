from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from loguru import logger
import os
from dotenv import load_dotenv

CONFIG_DIR = Path(__file__).parent
env_file_path = CONFIG_DIR / ".env"

# Load root project .env first
root_env_path = Path(__file__).parent.parent.parent.parent / ".env"
if root_env_path.exists():
    load_dotenv(root_env_path, override=False)
    logger.info(f"Loaded root .env from {root_env_path.resolve()}")

# Then load local .env (can override)
env_file = str(env_file_path)
if env_file_path.exists():
    load_dotenv(env_file_path, override=True)
    logger.warning(f"Using local .env file at {env_file_path.resolve()} for configuration.")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=env_file, env_file_encoding="utf-8")

    openrouter_api_key: Optional[str] = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Read CODE_MODEL from .env files, fallback to default
    openrouter_model: str = os.getenv("CODE_MODEL", "deepseek/deepseek-r1-distill-llama-70b:free")

    openai_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"

    max_tokens: int = 2000
    temperature: float = 0.1

    host: str = "localhost"
    port: int = 10001

settings = Settings()
logger.info(f"Code Agent using model: {settings.openrouter_model}")
