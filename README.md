# Krishi Mitra — Voice-First Agricultural Assistant

**Developed by Darshan Bhabad**

A student-project implementation of a Hindi/Marathi agricultural information
assistant. It prioritizes approved source documents and explicit refusals over
guessing. It includes a FastAPI backend, a responsive React/Vite frontend,
SQLite/PostgreSQL persistence, optional Qdrant hybrid retrieval, live weather,
an extensible mandi adapter, speech adapters, document administration, and a
small local evaluation suite.

> **Safety note:** The included knowledge file is demo content, not official
> agricultural advice. Verify publisher and date before approving documents.
> The system refuses chemical dosage recommendations and unsupported answers.

## Run locally

Requirements: Python 3.11+, Node.js 20+, and npm.

1. Keep your API key in the ignored `.env` file. If you need a template, copy
   `.env.example` to `.env`. The starter workspace's existing `URL` and
   `API_Key` settings are supported; no credentials are needed for demo mode.
2. Install backend packages and start the API:

   ```sh
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r backend/requirements.txt
   uvicorn app.main:app --app-dir backend --reload --port 8000
   ```

3. In another terminal, install frontend packages and start the UI:

   ```sh
   cd frontend
   npm install
   npm run dev
   ```

4. Open <http://localhost:5173>. API documentation is at
   <http://localhost:8000/docs>.

The app remains in demo mode until `API_KEY`, `BASE_URL`, and the exact
provider-supplied `MODEL_ID` are configured and `DEMO_MODE=false` is set. The
current `.env` has the API key and URL aliases but no model ID, so demo mode is
the expected startup behavior. Add the model ID your provider gave you; the
project deliberately does not guess it. Embeddings, transcription, and TTS
require separate model IDs. TTS also requires a provider-supported `TTS_VOICE`.

## What works in demo mode

- The text chat, saved sessions, Hindi/Marathi selector, document upload and
  approval workflow, and local evaluation interface.
- Unverified agricultural requests are refused; the bundled sample is visibly
  marked demo-only and provides no crop recommendations.
- Weather queries can use Open-Meteo when internet is available.
- Voice controls stay unavailable until speech model configuration is supplied.

For live model answers, approve authentic official documents first. Optional
Qdrant plus a configured multilingual embedding model enables vector search;
otherwise the retriever uses lexical ranking. Mandi data requires an authorized
provider endpoint configured with `MANDI_API_URL`.

## Tests and checks

```sh
cd backend
python -m pytest -q
cd ..
npm run build --prefix frontend
python scripts/evaluate.py
```

The evaluation reports local retrieval/refusal metrics and clearly leaves
faithfulness, speech accuracy, and provider reliability unmeasured when no
reference data is available. See [docs/deployment.md](./docs/deployment.md),
[docs/architecture.md](./docs/architecture.md), [docs/api.md](./docs/api.md),
and [docs/evaluation.md](./docs/evaluation.md).
