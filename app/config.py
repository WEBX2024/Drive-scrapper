"""
config.py — Application configuration.

Loads environment variables from .env, validates required keys,
and exposes a typed Settings object used across the application.
"""

import os
import logging
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths (derived dynamically from this file's location)
# ---------------------------------------------------------------------------
BASE_DIR: Path = Path(__file__).resolve().parent.parent
"""Root directory of the project (genai-drive-summarizer/)."""

DOWNLOAD_DIR: Path = BASE_DIR / "data" / "downloads"
"""Directory where downloaded Drive files are stored."""

PROMPTS_DIR: Path = Path(__file__).resolve().parent / "prompts"
"""Directory containing prompt template files."""

TEMPLATES_DIR: Path = BASE_DIR / "templates"
"""Directory containing Jinja2 HTML templates."""

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------
_env_path: Path = BASE_DIR / ".env"
load_dotenv(dotenv_path=_env_path)

# ---------------------------------------------------------------------------
# Required environment variable names
# ---------------------------------------------------------------------------
_REQUIRED_VARS: list[str] = [
    "GROQ_API_KEY",
    "GROQ_MODEL",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_REDIRECT_URI",
]


@dataclass(frozen=True)
class Settings:
    """Immutable application settings loaded from environment variables."""

    groq_api_key: str
    groq_model: str
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    max_files_cap: int


def _load_settings() -> Settings:
    """Validate and load all required settings from the environment.

    Raises:
        RuntimeError: If any required environment variable is missing or empty.

    Returns:
        A frozen Settings instance.
    """
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


# Singleton — validates at import time so the app fails fast.
logger = logging.getLogger(__name__)
settings: Settings = _load_settings()
logger.info("Configuration loaded successfully.")
