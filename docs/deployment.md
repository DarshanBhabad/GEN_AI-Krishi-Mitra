# Setup and deployment — Krishi Mitra

## Local development (Mac/Linux)

Requirements: Python 3.11+, Node.js 20+, and npm. No GPU is required.

1. Copy `.env.example` to `.env` only if you do not already have a local `.env`.
   Keep the real API key only in that ignored file. This project also reads the
   existing `URL` and `API_Key` names as aliases for `BASE_URL` and `API_KEY`.
2. Create and activate a Python virtual environment, then install backend
   dependencies:

   ```sh
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r backend/requirements.txt
   ```

3. Start the backend from the workspace root:

   ```sh
   uvicorn app.main:app --app-dir backend --reload --port 8000
   ```

4. In a second terminal:

   ```sh
   cd frontend
   npm install
   npm run dev
   ```

5. Open `http://localhost:5173`. FastAPI docs are at `http://localhost:8000/docs`.

The app starts in demo mode unless all of `API_KEY`, `BASE_URL`, and `MODEL_ID`
are configured and `DEMO_MODE=false` is set. Your current `.env` uses compatible
legacy names `URL` and `API_Key`; add the exact `MODEL_ID` supplied by your API
provider and set `DEMO_MODE=false` to enable model answers. Do not copy model IDs
from examples or assume every provider model supports every operation.

The OpenAI-compatible base URL should normally end at the API base (for example
the provider's `/v1` path). A full `/chat/completions` URL is also normalized.
Embedding, ASR, TTS, and TTS voice are configured separately. An unsupported
operation returns an explicit unavailable error; it is not silently replaced.

### Optional speech OCR support

Common audio types (WAV, MP3, M4A, WebM, OGG, FLAC) are forwarded to the configured
transcription provider. Scanned PDFs use OCR when Tesseract and Hindi/Marathi
language data are installed. On macOS, install Tesseract and its `hin`, `mar`,
and `eng` trained data using your package manager. If OCR is unavailable, PDF
ingestion reports the setup error instead of silently indexing empty text.

### Optional local vector search

Run Qdrant with `docker compose up qdrant -d`, set `QDRANT_URL=http://localhost:6333`,
and set `EMBEDDING_MODEL_ID` to a provider-supported multilingual embedding model.
Without both settings the application uses BM25-style lexical search. Qdrant
connection/indexing errors are surfaced in server logs and document approval.

### Live data

- Weather uses Open-Meteo geocoding and forecast endpoints and requires internet.
- Mandi prices remain unavailable until you configure `MANDI_API_URL` for an
  authorized provider. The adapter sends `commodity` and optional `market`
  query parameters and displays the returned JSON with retrieval time. Adapt this
  contract to the selected provider before relying on its data.

### Admin safety

Set a strong `ADMIN_TOKEN` before sharing the app. Document approval is a
trust decision: only approve documents whose source and publication are checked.
Bind the development server to localhost; do not expose this student MVP directly
to the public internet.

## Docker Compose

Ensure `.env` exists, then run:

```sh
docker compose up --build
```

Open `http://localhost:8080`; API docs are at `http://localhost:8000/docs`.
Compose runs PostgreSQL and Qdrant. The development database password in the
Compose file is for local-only use; replace it and configure secrets safely
before deployment.
