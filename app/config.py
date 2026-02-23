# config.py — Loads .env, validates required keys, and exposes a typed Settings object

import os
import logging
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

# Paths (derived from this file's location)
BASE_DIR: Path = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR: Path = BASE_DIR / "data" / "downloads"
PROMPTS_DIR: Path = Path(__file__).resolve().parent / "prompts"
TEMPLATES_DIR: Path = BASE_DIR / "templates"

# Load .env
_env_path: Path = BASE_DIR / ".env"
load_dotenv(dotenv_path=_env_path)

# Required environment variable names
_REQUIRED_VARS: list[str] = [
    "GROQ_API_KEY",
    "GROQ_MODEL",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_REDIRECT_URI",
]


@dataclass(frozen=True)
class Settings:
    """Immutable application settings from environment variables."""

    groq_api_key: str
    groq_model: str
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    max_files_cap: int


def _load_settings() -> Settings:
    """Validate required env vars and return a frozen Settings instance."""
    missing: list[str] = [v for v in _REQUIRED_VARS if not os.getenv(v)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Please set them in {_env_path}"
        )

    return Settings(
        groq_api_key=os.environ["GROQ_API_KEY"],
        groq_model=os.environ["GROQ_MODEL"],
        google_client_id=os.environ["GOOGLE_CLIENT_ID"],
        google_client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        google_redirect_uri=os.environ["GOOGLE_REDIRECT_URI"],
        max_files_cap=int(os.getenv("MAX_FILES_CAP", "100")),
    )


# Singleton — validates at import time for fast failure
logger = logging.getLogger(__name__)
settings: Settings = _load_settings()
logger.info("Configuration loaded successfully.")
