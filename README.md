# GenAI Drive Summarizer

A minimal FastAPI application that connects to Google Drive, reads **all** accessible `.pdf`, `.docx`, and `.txt` files, extracts text, and generates AI-powered summaries using **Groq** inference. Results are presented in a clean HTML table with CSV export.

---

## Features

- **Google Drive OAuth2** — securely connect to your Drive account
- **Full-drive processing** — scans all accessible files, not just one folder
- **Safety cap** — configurable limit (default 100) prevents runaway processing
- **Multi-format parsing** — PDF (pdfplumber), DOCX (python-docx), TXT
- **AI summarization** — concise 5–10 sentence summaries via Groq
- **Smart chunking** — handles long documents by splitting and re-summarizing
- **HTML results view** — clean, responsive summary table
- **CSV export** — one-click download of all summaries

---

## Project Structure

```
genai-drive-summarizer/
├── app/
│   ├── main.py                 # FastAPI routes & pipeline
│   ├── config.py               # Environment config & validation
│   ├── services/
│   │   ├── drive_service.py    # Google Drive OAuth2 & file ops
│   │   ├── parser_service.py   # Text extraction (PDF/DOCX/TXT)
│   │   └── summary_service.py  # Groq summarization
│   ├── utils/
│   │   └── file_utils.py       # File & text helpers
│   └── prompts/
│       └── summarization.txt   # Prompt template
├── templates/
│   └── results.html            # HTML results page
├── data/
│   └── downloads/              # Downloaded Drive files
├── .env                        # Environment variables (not committed)
├── .env.example                # Example environment file
├── requirements.txt            # Python dependencies
├── run.ps1                     # PowerShell launch script
└── README.md
```

---

## Prerequisites

- Python 3.10+
- A Google Cloud project with the **Drive API** enabled
- OAuth2 credentials (Web application type) from the [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
- A [Groq API key](https://console.groq.com/keys)

---

## Setup

### 1. Clone & install dependencies

```bash
git clone <repo-url>
cd genai-drive-summarizer
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy the example file and fill in your values:

```bash
copy .env.example .env
```

Edit `.env`:

| Variable               | Description                                     | Required |
| ---------------------- | ----------------------------------------------- | -------- |
| `GROQ_API_KEY`         | Your Groq API key                               | ✅       |
| `GROQ_MODEL`           | Groq model name (e.g. `llama-3.1-8b-instant`)   | ✅       |
| `GOOGLE_CLIENT_ID`     | OAuth2 client ID from Google Cloud Console      | ✅       |
| `GOOGLE_CLIENT_SECRET` | OAuth2 client secret                            | ✅       |
| `GOOGLE_REDIRECT_URI`  | Must match the registered redirect URI          | ✅       |
| `MAX_FILES_CAP`        | Maximum files to process per run (default: 100) | Optional |

### 3. Configure Google Cloud

1. Go to **APIs & Services → Credentials** in the Google Cloud Console.
2. Create an **OAuth 2.0 Client ID** (Web application).
3. Add `http://localhost:8000/auth/callback` as an authorised redirect URI.
4. Enable the **Google Drive API** under **APIs & Services → Library**.

---

## Running the Application

### PowerShell (recommended)

```powershell
.\run.ps1
```

### Manual

```bash
venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

Then open **http://localhost:8000** in your browser.

---

## Usage

1. Click **Connect to Google Drive** on the landing page.
2. Authorize access via your Google account.
3. Click **▶ Process Files** to run the pipeline.
4. View summaries on the **Results** page.
5. Click **⬇ Download CSV** to export.

> **Note:** The app processes **all** supported files visible to you in Google Drive (not limited to a single folder). A safety cap (default 100 files) prevents excessive API usage on large drives. Adjust `MAX_FILES_CAP` in `.env` as needed.

---

## Example Output

| #   | File Name          | Summary                                                   |
| --- | ------------------ | --------------------------------------------------------- |
| 1   | report_q4.pdf      | This document presents the Q4 financial results for …     |
| 2   | meeting_notes.docx | The meeting covered three main topics: project timeline … |
| 3   | requirements.txt   | The file lists the Python dependencies required for …     |

---

## License

This project is provided as-is for educational and internal use.
