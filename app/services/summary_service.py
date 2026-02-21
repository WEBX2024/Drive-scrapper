"""
summary_service.py — Groq-powered document summarization.

Loads the prompt template dynamically from the prompts directory,
handles safe chunking for long documents, and returns structured results.
"""

import logging
from pathlib import Path

from groq import Groq

from app.config import settings, PROMPTS_DIR

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (tuneable)
# ---------------------------------------------------------------------------
_TEMPERATURE: float = 0.2  # Low temperature for deterministic output
_MAX_CHUNK_CHARS: int = 10_000  # ~3 000 tokens at ~3.3 chars/token
_REQUEST_TIMEOUT: float = 60.0  # seconds


# ---------------------------------------------------------------------------
# Prompt loading (dynamic from file)
# ---------------------------------------------------------------------------

def _load_prompt_template() -> str:
    """Read the summarization prompt template from disk.

    Returns:
        The raw prompt string containing a ``{document_text}`` placeholder.

    Raises:
        FileNotFoundError: If the prompt file is missing.
    """
    prompt_path: Path = PROMPTS_DIR / "summarization.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Prompt template not found at {prompt_path}. "
            "Please create app/prompts/summarization.txt."
        )
    return prompt_path.read_text(encoding="utf-8")


# Load once at module level for reuse across calls.
_PROMPT_TEMPLATE: str = _load_prompt_template()


# ---------------------------------------------------------------------------
# Chunking helper
# ---------------------------------------------------------------------------

def _chunk_text(text: str, max_chars: int = _MAX_CHUNK_CHARS) -> list[str]:
    """Split text into chunks that fit within the token budget.

    Splits on sentence boundaries when possible to avoid cutting mid-sentence.

    Args:
        text: Full document text.
        max_chars: Maximum characters per chunk.

    Returns:
        A list of text chunks.
    """
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    while text:
        if len(text) <= max_chars:
            chunks.append(text)
            break

        # Try to split at the last sentence-ending punctuation within the limit
        split_idx = max_chars
        for sep in (".", "!", "?"):
            idx = text.rfind(sep, 0, max_chars)
            if idx != -1:
                split_idx = idx + 1  # include the punctuation
                break

        chunks.append(text[:split_idx].strip())
        text = text[split_idx:].strip()

    return chunks


# ---------------------------------------------------------------------------
# Groq API call
# ---------------------------------------------------------------------------

def _call_groq(prompt: str) -> str:
    """Send a prompt to the Groq Chat Completions API and return the reply.

    Args:
        prompt: The fully assembled user prompt string.

    Returns:
        The model's response text.

    Raises:
        RuntimeError: If the API call fails, times out, or returns empty.
    """
    client = Groq(api_key=settings.groq_api_key)
    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            temperature=_TEMPERATURE,
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional document summarizer.",
                },
                {"role": "user", "content": prompt},
            ],
            timeout=_REQUEST_TIMEOUT,
        )
    except Exception as exc:
        raise RuntimeError(f"Groq API call failed: {exc}") from exc

    content = response.choices[0].message.content
    if not content or not content.strip():
        raise RuntimeError("Groq API returned an empty response.")
    return content.strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def summarize_text(file_name: str, text: str) -> dict[str, str]:
    """Generate a concise summary of the given document text.

    For long documents the text is split into chunks, each chunk is
    summarized individually, and the partial summaries are combined into
    a single final summary.

    Args:
        file_name: Original file name (for the result dict).
        text: Extracted document text.

    Returns:
        A dict with ``file_name`` and ``summary`` keys.
    """
    if not text.strip():
        logger.warning("Empty text provided for '%s'. Skipping summarization.", file_name)
        return {"file_name": file_name, "summary": "No content available for summarization."}

    chunks = _chunk_text(text)
    logger.info(
        "Summarizing '%s' — %d chunk(s), %d total characters.",
        file_name, len(chunks), len(text),
    )

    if len(chunks) == 1:
        # Single-chunk path — one API call
        prompt = _PROMPT_TEMPLATE.format(document_text=chunks[0])
        summary = _call_groq(prompt)
    else:
        # Multi-chunk path: summarize each chunk, then combine
        partial_summaries: list[str] = []
        for i, chunk in enumerate(chunks, start=1):
            logger.debug("  Chunk %d/%d (%d chars)", i, len(chunks), len(chunk))
            prompt = _PROMPT_TEMPLATE.format(document_text=chunk)
            partial_summaries.append(_call_groq(prompt))

        # Combine partial summaries into one final summary
        combined = "\n\n".join(partial_summaries)
        combine_prompt = _PROMPT_TEMPLATE.format(document_text=combined)
        summary = _call_groq(combine_prompt)

    logger.info("Summary generated for '%s'.", file_name)
    return {"file_name": file_name, "summary": summary}
