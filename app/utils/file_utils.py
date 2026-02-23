# file_utils.py — Lightweight file-system and text helpers

import os
import re
from pathlib import Path


def get_file_extension(filename: str) -> str:
    """Return the lowercase file extension without the leading dot."""
    _, ext = os.path.splitext(filename)
    return ext.lstrip(".").lower()


def ensure_directory(path: str | Path) -> Path:
    """Create a directory (and parents) if it doesn't already exist."""
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def clean_text(text: str) -> str:
    """Collapse whitespace runs and strip edges from raw text."""
    if not text:
        return ""
    # Collapse whitespace into single spaces
    cleaned = re.sub(r"\s+", " ", text)
    return cleaned.strip()
