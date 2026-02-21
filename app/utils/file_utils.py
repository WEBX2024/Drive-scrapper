"""
file_utils.py — Lightweight file-system and text helpers.

Provides safe extension detection, directory creation, and text cleaning
used across service modules.
"""

import os
import re
from pathlib import Path


def get_file_extension(filename: str) -> str:
    """Return the lowercase file extension without the leading dot.

    Args:
        filename: The file name or path string.

    Returns:
        Lowercase extension (e.g. ``"pdf"``), or an empty string if none.
    """
    _, ext = os.path.splitext(filename)
    return ext.lstrip(".").lower()


def ensure_directory(path: str | Path) -> Path:
    """Create a directory (and parents) if it does not already exist.

    Args:
        path: Target directory path.

    Returns:
        The resolved ``Path`` object.
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def clean_text(text: str) -> str:
    """Normalise extracted text by collapsing whitespace and stripping edges.

    Args:
        text: Raw text content.

    Returns:
        Cleaned text with runs of whitespace collapsed to single spaces.
    """
    if not text:
        return ""
    # Replace any sequence of whitespace (including newlines) with a single space
    cleaned = re.sub(r"\s+", " ", text)
    return cleaned.strip()
