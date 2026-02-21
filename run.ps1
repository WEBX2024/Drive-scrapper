# GenAI Drive Summarizer — Launch Script
# Activates the virtual environment and starts the FastAPI server.

# Activate the virtual environment
& "$PSScriptRoot\venv\Scripts\Activate.ps1"

# Start the Uvicorn server with auto-reload
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
