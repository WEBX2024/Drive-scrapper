# parser_service.py — Unified text extraction from supported file types (PDF, DOCX, TXT)

import logging
from pathlib import Path

import pdfplumber
from docx import Document

from app.utils.file_utils import get_file_extension, clean_text

logger = logging.getLogger(__name__)

# Per-type extractors

def _extract_pdf(file_path: str) -> str:
    """Extract text from a PDF using pdfplumber."""
    pages_text: list[str] = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
    return "\n".join(pages_text)


def _extract_docx(file_path: str) -> str:
    """Extract text from a DOCX using python-docx."""
    doc = Document(file_path)
    return "\n".join(para.text for para in doc.paragraphs if para.text)


def _extract_txt(file_path: str) -> str:
    """Read the full contents of a plain-text file."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


# Extractor dispatch table
_EXTRACTORS: dict[str, callable] = {
    "pdf": _extract_pdf,
    "docx": _extract_docx,
    "txt": _extract_txt,
}


# Public API

def extract_text(file_path: str) -> str:
    """Detect file type, extract text via the appropriate parser, and return cleaned content."""
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
