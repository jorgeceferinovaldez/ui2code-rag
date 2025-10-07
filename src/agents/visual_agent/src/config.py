from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from loguru import logger
import os
from dotenv import load_dotenv

CONFIG_DIR = Path(__file__).parent
env_file_path = CONFIG_DIR / ".env"

# Also check root project .env
root_env_path = Path(__file__).parent.parent.parent.parent / ".env"

# Load root .env first if it exists
if root_env_path.exists():
    load_dotenv(root_env_path, override=False)  # Don't override existing env vars
    logger.info(f"Loaded root .env from {root_env_path.resolve()}")

# Then load local .env (can override root settings)
env_file = str(env_file_path)
if env_file_path.exists():
    load_dotenv(env_file_path, override=True)  # Local .env overrides root
    logger.warning(f"Using local .env file at {env_file_path.resolve()} for configuration.")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=env_file, env_file_encoding="utf-8")

    openrouter_api_key: Optional[str] = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Read VISUAL_MODEL from .env files (loaded above), fallback to default
    openrouter_model: str = os.getenv("VISUAL_MODEL", "google/gemini-2.0-flash-exp:free")

    openai_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"

    host: str = "localhost"
    port: int = 10000


settings = Settings()
logger.info(f"Visual Agent using model: {settings.openrouter_model}")
