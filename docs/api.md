# API reference — Krishi Mitra

The interactive OpenAPI page is at `http://localhost:8000/docs`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Database and app health |
| GET | `/api/config` | Non-sensitive capability flags |
| POST | `/api/chat` | Grounded text question |
| GET | `/api/sessions/{session_id}` | Retrieve saved chat history |
| POST | `/api/voice` | Transcribe audio, answer, and optionally synthesize speech |
| POST | `/api/speech` | Synthesize configured text-to-speech |
| GET | `/api/documents` | List documents and review status |
| POST | `/api/documents/upload` | Upload UTF-8 text, Markdown, or PDF |
| POST | `/api/documents/{id}/approve` | Approve a document for retrieval |
| POST | `/api/evaluation/run` | Run the bundled local evaluation cases |

## Chat request

```json
{
  "question": "आज का मौसम कैसा है?",
  "language": "hi",
  "location": "Pune",
  "session_id": null
}
```

`language` is `hi` or `mr`. `location` is needed for weather/market questions
unless a suitable location is entered in the UI. The response includes an
`answer`, a `verification` state (`verified`, `uncertain`, `unavailable`, or
`demo`), a refusal `reason`, source references, and optional live data.

## Document administration

If `ADMIN_TOKEN` is configured, send `Authorization: Bearer <token>` for uploads
and approvals. Without a token, those actions are open for local development;
set a token before any shared or deployed use. Uploads remain pending until an
administrator approves them.
