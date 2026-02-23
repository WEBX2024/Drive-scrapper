# summary_service.py — Groq-powered document summarization with chunking support

import logging
from pathlib import Path

from groq import Groq

from app.config import settings, PROMPTS_DIR

logger = logging.getLogger(__name__)

# Tuneable constants
_TEMPERATURE: float = 0.2   # low temp for deterministic output
_MAX_CHUNK_CHARS: int = 10_000  # ~3k tokens
_REQUEST_TIMEOUT: float = 60.0  # API timeout in seconds


# Prompt loading

def _load_prompt_template() -> str:
    """Read the summarization prompt template from disk."""
    prompt_path: Path = PROMPTS_DIR / "summarization.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Prompt template not found at {prompt_path}. "
            "Please create app/prompts/summarization.txt."
        )
    return prompt_path.read_text(encoding="utf-8")


# Load once at module level for reuse
_PROMPT_TEMPLATE: str = _load_prompt_template()


# Chunking helper

def _chunk_text(text: str, max_chars: int = _MAX_CHUNK_CHARS) -> list[str]:
    """Split text into chunks on sentence boundaries to fit the token budget."""
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    while text:
        if len(text) <= max_chars:
            chunks.append(text)
            break

        # Split at last sentence-ending punctuation within limit
        split_idx = max_chars
        for sep in (".", "!", "?"):
            idx = text.rfind(sep, 0, max_chars)
            if idx != -1:
                split_idx = idx + 1  # include the punctuation
                break

        chunks.append(text[:split_idx].strip())
        text = text[split_idx:].strip()

    return chunks


# Groq API call

def _call_groq(prompt: str) -> str:
    """Send a prompt to Groq Chat Completions API and return the reply."""
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


# Public API

def summarize_text(file_name: str, text: str) -> dict[str, str]:
    """Summarize document text (chunks long docs); returns {file_name, summary}."""
    if not text.strip():
        logger.warning("Empty text provided for '%s'. Skipping summarization.", file_name)
        return {"file_name": file_name, "summary": "No content available for summarization."}

    chunks = _chunk_text(text)
    logger.info(
        "Summarizing '%s' — %d chunk(s), %d total characters.",
        file_name, len(chunks), len(text),
    )

    if len(chunks) == 1:
        # Single-chunk: one API call
        prompt = _PROMPT_TEMPLATE.format(document_text=chunks[0])
        summary = _call_groq(prompt)
    else:
        # Multi-chunk: summarize each, then combine
        partial_summaries: list[str] = []
        for i, chunk in enumerate(chunks, start=1):
            logger.debug("  Chunk %d/%d (%d chars)", i, len(chunks), len(chunk))
            prompt = _PROMPT_TEMPLATE.format(document_text=chunk)
            partial_summaries.append(_call_groq(prompt))

        # Combine partials into one final summary
        combined = "\n\n".join(partial_summaries)
        combine_prompt = _PROMPT_TEMPLATE.format(document_text=combined)
        summary = _call_groq(combine_prompt)

    logger.info("Summary generated for '%s'.", file_name)
    return {"file_name": file_name, "summary": summary}
