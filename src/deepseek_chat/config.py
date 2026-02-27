import logging
from pathlib import Path

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Project root: deepseek-chat/ (3 levels up from this file: config.py -> deepseek_chat/ -> src/ -> deepseek-chat/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


MODELS = {
    "deepseek-chat": {
        "name": "DeepSeek Chat",
        "description": "General chat, $0.14/$0.28 per M tokens",
        "input_cost": 0.14,
        "output_cost": 0.28,
    },
    "deepseek-reasoner": {
        "name": "DeepSeek Reasoner",
        "description": "Deep reasoning (R1), $0.55/$2.19 per M tokens",
        "input_cost": 0.55,
        "output_cost": 2.19,
    },
}

# Models that don't support temperature/top_p
REASONING_MODELS = {"deepseek-reasoner"}


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DEEPSEEK_",
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API
    api_key: str = Field(..., alias="DEEPSEEK_API_KEY")
    api_base_url: str = "https://api.deepseek.com"

    # Model defaults
    default_model: str = "deepseek-chat"
    temperature: float = 0.2
    max_tokens: int = 4096
    top_p: float = 0.9

    # System prompt
    system_prompt: str = "Be helpful, accurate, and concise."

    # Paths
    db_path: Path = Path("~/.local/share/deepseek-chat/history.db").expanduser()
    log_path: Path = Path("~/.local/share/deepseek-chat/dschat.log").expanduser()
    export_dir: Path = Path("~/Desktop").expanduser()

    # UI
    show_cost: bool = True
    show_reasoning: bool = True

    @field_validator("default_model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        if v not in MODELS:
            valid = ", ".join(MODELS.keys())
            raise ValueError(f"Unknown model '{v}'. Valid models: {valid}")
        return v


def load_config() -> AppConfig:
    """Load config from .env, then overlay with yaml if it exists."""
    yaml_path = Path("~/.config/deepseek-chat/config.yaml").expanduser()
    yaml_overrides = {}
    if yaml_path.exists():
        try:
            with open(yaml_path, encoding="utf-8") as f:
                yaml_overrides = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            logger.warning("Invalid YAML config, using defaults: %s", e)
        except OSError as e:
            logger.warning("Cannot read config file, using defaults: %s", e)
    return AppConfig(**yaml_overrides)
