# SourceSync

SourceSync is a temporary-session hybrid RAG application for English PDF/TXT
documents and public GitHub repositories. It combines dense retrieval, BM25,
Reciprocal Rank Fusion, and source-grounded Gemini responses.

## Project layout

- `backend/` — FastAPI API and RAG pipeline
- `frontend/` — React + Vite JavaScript interface
- `.env` — local credentials (not committed)

## Local development

From the repository root, start the backend:

```powershell
Set-Location backend
uv run uvicorn app.main:app --reload --port 8000
```

In a second terminal, start the frontend:

```powershell
Set-Location frontend
npm run dev
```

Run the backend validation suite from the repository root:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Copy `.env.example` to `.env` and add the Qdrant and Gemini values before using
ingestion or question answering.

## Deployment on Render

The repository includes `render.yaml` for two services:

- `sourcesync-api` — FastAPI web service
- `sourcesync-frontend` — React static site

After creating the services, set these values in Render:

1. Backend `QDRANT_URL`, `QDRANT_API_KEY`, and `GEMINI_API_KEY`.
2. Backend `CORS_ORIGINS` to the deployed frontend URL.
3. Frontend `VITE_API_BASE_URL` to the deployed backend URL.
4. Keep `SESSION_COOKIE_SECURE=true` on the HTTPS Render backend; it remains
	`false` in local development.

The application uses anonymous in-memory sessions that expire after 60 minutes.
No login, Redis, queue, or worker service is required for this version.

## Current limits

- PDF/TXT documents: 25 MB and 150 PDF pages maximum
- GitHub archives: 50 MB maximum
- GitHub repositories: 5,000 eligible files maximum
- Individual repository files: 1 MB maximum
