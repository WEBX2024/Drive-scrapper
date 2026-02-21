"""
parser_service.py — Unified text extraction from supported file types.

Provides a single ``extract_text()`` entry-point that detects the file type
and delegates to the appropriate parser (pdfplumber, python-docx, or plain
text reader).
"""

import logging
from pathlib import Path

import pdfplumber
from docx import Document

from app.utils.file_utils import get_file_extension, clean_text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-type extractors (private)
# ---------------------------------------------------------------------------

def _extract_pdf(file_path: str) -> str:
    """Extract text from a PDF file using pdfplumber.

    Args:
        file_path: Absolute path to the PDF file.

    Returns:
        Concatenated text from all pages.
    """
    pages_text: list[str] = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
    return "\n".join(pages_text)


def _extract_docx(file_path: str) -> str:
    """Extract text from a DOCX file using python-docx.

    Args:
        file_path: Absolute path to the DOCX file.

    Returns:
        Concatenated paragraph text.
    """
    doc = Document(file_path)
    return "\n".join(para.text for para in doc.paragraphs if para.text)


def _extract_txt(file_path: str) -> str:
    """Read the full contents of a plain-text file.

    Args:
        file_path: Absolute path to the TXT file.

    Returns:
        File content as a string.
    """
    with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# Extractor dispatch table (dynamic — add new types here)
# ---------------------------------------------------------------------------
_EXTRACTORS: dict[str, callable] = {
    "pdf": _extract_pdf,
    "docx": _extract_docx,
    "txt": _extract_txt,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_text(file_path: str) -> str:
    """Extract and clean text from a supported file.

    Detects the file type by extension, delegates to the appropriate parser,
    and returns cleaned text.

    Args:
        file_path: Absolute path to the file.

    Returns:
        Cleaned, whitespace-normalised text content.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file extension is unsupported.
        RuntimeError: If extraction fails for any other reason.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if path.stat().st_size == 0:
        logger.warning("File is empty: %s", file_path)
        return ""

    ext = get_file_extension(path.name)
    extractor = _EXTRACTORS.get(ext)

    if extractor is None:
        supported = ", ".join(sorted(_EXTRACTORS.keys()))
        raise ValueError(
            f"Unsupported file type '.{ext}'. Supported types: {supported}"
        )

    try:
        raw_text: str = extractor(file_path)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to extract text from '{path.name}': {exc}"
        ) from exc

    cleaned = clean_text(raw_text)
    logger.info(
        "Extracted %d characters from '%s'.", len(cleaned), path.name
    )
    return cleaned
