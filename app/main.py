"""
main.py — FastAPI application entry-point.

Defines routes for the GenAI Document Summarizer pipeline:
  /              → Landing page
  /auth/callback → OAuth2 callback
  /process       → Run the full pipeline (background)
  /processing    → Live progress page with stop button
  /process/status → JSON progress polling
  /process/stop  → Stop the current scan
  /results       → View summaries in an HTML table
  /download      → Export summaries as CSV
  /download/pdf  → Export summaries as PDF
"""

import csv
import io
import logging
import threading
from typing import Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fpdf import FPDF

from app.config import TEMPLATES_DIR
from app.services import drive_service, parser_service, summary_service

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App & templates
# ---------------------------------------------------------------------------
app = FastAPI(
    title="GenAI Drive Summarizer",
    description="Summarize Google Drive documents using Groq.",
    version="1.0.0",
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# ---------------------------------------------------------------------------
# In-memory state (reset each server restart)
# ---------------------------------------------------------------------------
_credentials_store: dict[str, Any] = {}
_summaries: list[dict[str, str]] = []

# Background processing state
_stop_requested = threading.Event()
_processing_lock = threading.Lock()
_processing_status: dict[str, Any] = {
    "is_running": False,
    "total": 0,
    "completed": 0,
    "current_file": "",
    "stopped": False,
}


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

def _run_pipeline(credentials):
    """Execute the pipeline in a background thread.

    Checks _stop_requested before processing each file so the user
    can halt the scan mid-run.  Partial results are kept.
    """
    global _summaries

    try:
        # 1. List files
        files = drive_service.list_files(credentials)
        if not files:
            logger.info("No supported files found in Drive folder.")
            with _processing_lock:
                _processing_status["is_running"] = False
                _processing_status["stopped"] = False
            return

        with _processing_lock:
            _processing_status["total"] = len(files)

        # 2-4. Download → Parse → Summarize each file
        results: list[dict[str, str]] = []
        for file_info in files:
            # ── Check stop flag BEFORE processing ──
            if _stop_requested.is_set():
                logger.info("Stop requested – halting pipeline after %d file(s).", len(results))
                with _processing_lock:
                    _processing_status["stopped"] = True
                break

            file_name: str = file_info["name"]
            file_id: str = file_info["id"]

            with _processing_lock:
                _processing_status["current_file"] = file_name

            logger.info("Processing '%s' …", file_name)

            try:
                local_path = drive_service.download_file(credentials, file_id, file_name)
                text = parser_service.extract_text(local_path)
                result = summary_service.summarize_text(file_name, text)
                results.append(result)
            except Exception as exc:
                logger.error("Failed to process '%s': %s", file_name, exc)
                results.append({"file_name": file_name, "summary": f"Error: {exc}"})

            with _processing_lock:
                _processing_status["completed"] = len(results)

        # 5. Store results (partial or complete)
        _summaries.clear()
        _summaries.extend(results)
        logger.info("Pipeline complete — %d file(s) processed.", len(results))

    except Exception as exc:
        logger.exception("Pipeline failed: %s", exc)
    finally:
        with _processing_lock:
            _processing_status["is_running"] = False
            _processing_status["current_file"] = ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index():
    """Landing page with a link to connect to Google Drive."""
    auth_url = drive_service.get_auth_url()
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>GenAI Drive Summarizer</title>
        <style>
            :root {{
                --bg: #f8f9fa;
                --card: #ffffff;
                --primary: #4285f4;
                --primary-hover: #3367d6;
                --text: #202124;
                --muted: #5f6368;
                --border: #dadce0;
                --success: #0f9d58;
            }}
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
                background: var(--bg);
                color: var(--text);
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
            }}
            .card {{
                background: var(--card);
                border: 1px solid var(--border);
                border-radius: 12px;
                padding: 48px 40px;
                max-width: 520px;
                text-align: center;
                box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            }}
            h1 {{ font-size: 1.75rem; margin-bottom: 12px; }}
            p {{ color: var(--muted); margin-bottom: 32px; line-height: 1.6; }}
            .btn {{
                display: inline-block;
                padding: 12px 32px;
                background: var(--primary);
                color: #fff;
                text-decoration: none;
                border-radius: 8px;
                font-weight: 600;
                font-size: 0.95rem;
                transition: background 0.2s;
                border: none;
                cursor: pointer;
            }}
            .btn:hover {{ background: var(--primary-hover); }}
            .btn-process {{
                background: var(--success);
                margin-left: 12px;
            }}
            .btn-process:hover {{ background: #0b8043; }}
            .actions {{ margin-top: 16px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>📄 GenAI Drive Summarizer</h1>
            <p>
                Connect your Google Drive, and this tool will read documents
                from your configured folder, extract the text, and generate
                concise AI-powered summaries.
            </p>
            <a class="btn" href="{auth_url}">Connect to Google Drive</a>
            <div class="actions">
                <form action="/process" method="post" style="display:inline;">
                    <button class="btn btn-process" type="submit">▶ Process Files</button>
                </form>
            </div>
        </div>
    </body>
    </html>
    """


@app.get("/auth/callback")
async def auth_callback(code: str | None = None, error: str | None = None):
    """Handle the OAuth2 redirect from Google.

    Exchanges the authorization code for credentials and stores them.
    """
    if error:
        logger.error("OAuth2 error: %s", error)
        raise HTTPException(status_code=400, detail=f"OAuth2 error: {error}")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code.")

    try:
        credentials = drive_service.exchange_code(code)
        _credentials_store["default"] = credentials
        logger.info("OAuth2 credentials stored.")
    except Exception as exc:
        logger.exception("Failed to exchange OAuth2 code.")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return RedirectResponse(url="/", status_code=302)


@app.post("/process")
async def process_files():
    """Launch the pipeline in a background thread and redirect to the progress page."""
    credentials = _credentials_store.get("default")
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated. Please connect to Google Drive first.",
        )

    with _processing_lock:
        if _processing_status["is_running"]:
            return RedirectResponse(url="/processing", status_code=303)

        # Reset state
        _stop_requested.clear()
        _processing_status["is_running"] = True
        _processing_status["total"] = 0
        _processing_status["completed"] = 0
        _processing_status["current_file"] = "Listing files…"
        _processing_status["stopped"] = False

    worker = threading.Thread(target=_run_pipeline, args=(credentials,), daemon=True)
    worker.start()

    return RedirectResponse(url="/processing", status_code=303)


@app.get("/processing", response_class=HTMLResponse)
async def processing_page(request: Request):
    """Render the live progress page with a stop button."""
    return templates.TemplateResponse("processing.html", {"request": request})


@app.get("/process/status")
async def process_status():
    """Return the current pipeline status as JSON (polled by the frontend)."""
    with _processing_lock:
        return JSONResponse(content=dict(_processing_status))


@app.post("/process/stop")
async def process_stop():
    """Signal the background worker to stop after the current file."""
    _stop_requested.set()
    logger.info("Stop signal sent.")
    return JSONResponse(content={"message": "Stop signal sent."})


@app.get("/results", response_class=HTMLResponse)
async def results_page(request: Request):
    """Render the summaries in an HTML table."""
    with _processing_lock:
        stopped = _processing_status["stopped"]
        total = _processing_status["total"]
    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "summaries": _summaries,
            "stopped": stopped,
            "total": total,
        },
    )


@app.get("/download")
async def download_csv():
    """Export current summaries as a CSV file."""
    if not _summaries:
        raise HTTPException(status_code=404, detail="No summaries available yet.")

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["file_name", "summary"])
    writer.writeheader()
    writer.writerows(_summaries)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=summaries.csv"},
    )


def _sanitize_for_pdf(text: str) -> str:
    """Replace common unicode characters with latin-1 safe equivalents."""
    replacements = {
        "\u2018": "'", "\u2019": "'",   # smart single quotes
        "\u201c": '"', "\u201d": '"',   # smart double quotes
        "\u2013": "-", "\u2014": "--",  # en-dash, em-dash
        "\u2026": "...",                # ellipsis
        "\u2022": "*",                  # bullet
        "\u00a0": " ",                  # non-breaking space
        "\u200b": "",                   # zero-width space
    }
    for uni, asc in replacements.items():
        text = text.replace(uni, asc)
    # Fallback: drop any remaining non-latin-1 chars
    return text.encode("latin-1", errors="replace").decode("latin-1")


@app.get("/download/pdf")
async def download_pdf():
    """Export current summaries as a PDF file."""
    if not _summaries:
        raise HTTPException(status_code=404, detail="No summaries available yet.")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Title page
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 20, "Document Summaries", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(
        0, 10,
        f"{len(_summaries)} file(s) summarized",
        new_x="LMARGIN", new_y="NEXT", align="C",
    )
    pdf.ln(10)

    # Each summary
    for i, item in enumerate(_summaries, start=1):
        file_name = _sanitize_for_pdf(item["file_name"])
        summary = _sanitize_for_pdf(item["summary"])

        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(
            0, 10,
            f"{i}. {file_name}",
            new_x="LMARGIN", new_y="NEXT",
        )
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, summary)
        pdf.ln(6)

    # Output to bytes
    pdf_bytes = pdf.output()
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=summaries.pdf"},
    )
