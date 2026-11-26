# Architecture — Krishi Mitra

The project is a small modular monolith: one FastAPI process, one React SPA, one
relational database, and an optional Qdrant service. It does not create one
microservice per capability.

## Request path

1. The frontend submits text or an audio file to FastAPI. It never receives API
   credentials.
2. The backend applies deterministic language/intent heuristics and explicit
   safety checks. Weather and market-price questions use their live-data adapters.
3. Other agricultural questions search only approved document chunks. The local
   retriever uses BM25-style lexical ranking; with an embedding model and Qdrant
   configured it combines lexical and vector rankings with Reciprocal Rank Fusion.
4. The confidence gate requires approved evidence and sufficient lexical query
   coverage. Chemical advice is refused before retrieval. A configured chat model
   receives only retrieved approved, non-demo evidence.
5. Session messages, documents, and chunks are stored through SQLAlchemy. The
   local default is SQLite; Docker Compose uses PostgreSQL.

## Trust boundaries and limitations

- Approval is a human admin action; the application does not independently verify
  the authenticity of a publisher. Verify each document before approving it.
- The bundled document is explicitly demo-only and contains no crop advice.
- A missing model ID keeps the app in demo mode. No model ID is guessed.
- Qdrant and multilingual embeddings are optional. Without both, search is
  lexical-only; the capability response makes this visible.
- The mandi adapter requires a configured authorized JSON endpoint. It does not
  claim to connect directly to Agmarknet/e-NAM without a supported contract.
- Weather uses Open-Meteo geocoding and forecast APIs and requires internet access.
- ASR/TTS run only when their model IDs (and TTS voice) are configured and the
  provider supports the corresponding API operation.
- Confidence is based on explicit policy and evidence retrieval, not a model-
  generated confidence score. ASR confidence is not available from every provider.
