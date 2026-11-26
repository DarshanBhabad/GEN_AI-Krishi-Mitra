import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  approveDocument,
  getConfig,
  getDocuments,
  getHistory,
  runEvaluation,
  sendChat,
  sendVoice,
  synthesizeSpeech,
  uploadDocument,
} from "./api";
import type {
  AppConfig,
  ChatResponse,
  DocumentItem,
  Language,
  Message,
  SavedConversation,
} from "./types";

const HISTORY_KEY = "krishi-mitra-history";
const CURRENT_KEY = "krishi-mitra-current";

function readHistory(): SavedConversation[] {
  try {
    const stored = localStorage.getItem(HISTORY_KEY);
    return stored ? JSON.parse(stored) as SavedConversation[] : [];
  } catch {
    return [];
  }
}

function verificationLabel(value?: Message["verification"]): string {
  switch (value) {
    case "verified": return "Live / source-backed";
    case "demo": return "Demo response";
    case "uncertain": return "Needs more information";
    default: return "Unavailable";
  }
}

function messageFromResponse(response: ChatResponse): Message {
  return {
    role: "assistant",
    content: response.answer,
    verification: response.verification,
    sources: response.sources,
    audio_base64: response.audio_base64,
    audio_mime: response.audio_mime,
  };
}

export default function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [language, setLanguage] = useState<Language>("hi");
  const [location, setLocation] = useState("");
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(() => localStorage.getItem(CURRENT_KEY));
  const [history, setHistory] = useState<SavedConversation[]>(readHistory);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [activePanel, setActivePanel] = useState<"chat" | "admin" | "evaluation">("chat");
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [adminToken, setAdminToken] = useState(() => localStorage.getItem("krishi-admin-token") ?? "");
  const [documentSource, setDocumentSource] = useState("");
  const [documentLanguage, setDocumentLanguage] = useState("unknown");
  const [documentDate, setDocumentDate] = useState("");
  const [documentCrop, setDocumentCrop] = useState("");
  const [documentRegion, setDocumentRegion] = useState("");
  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [evaluation, setEvaluation] = useState<Record<string, unknown> | null>(null);
  const [recording, setRecording] = useState(false);
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const audioChunks = useRef<Blob[]>([]);
  const historyEnd = useRef<HTMLDivElement>(null);
  const chatLabel = language === "hi" ? "Krishi Mitra" : "Krishi Mitra";

  useEffect(() => {
    getConfig().then(setConfig).catch((cause: Error) => setError(cause.message));
    getDocuments().then(setDocuments).catch((cause: Error) => setError(cause.message));
  }, []);

  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      return;
    }
    getHistory(sessionId)
      .then((result) => {
        setLanguage(result.language);
        setMessages(result.messages.map((message) => ({
          role: message.role,
          content: message.content,
          verification: message.verification as Message["verification"],
          sources: message.sources,
        })));
      })
      .catch(() => {
        setSessionId(null);
        localStorage.removeItem(CURRENT_KEY);
      });
  }, []);

  useEffect(() => {
    historyEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  function persistConversation(id: string, nextMessages: Message[]) {
    const firstUserMessage = nextMessages.find((message) => message.role === "user")?.content ?? "New conversation";
    const entry: SavedConversation = {
      id,
      label: firstUserMessage.slice(0, 48),
      messages: nextMessages.map(({ audio_base64: _audio, audio_mime: _mime, ...message }) => message),
    };
    setHistory((previous) => {
      const next = [entry, ...previous.filter((item) => item.id !== id)].slice(0, 12);
      localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
      return next;
    });
    localStorage.setItem(CURRENT_KEY, id);
  }

  async function submitQuestion(text = question) {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setError("");
    setBusy(true);
    const nextMessages = [...messages, { role: "user" as const, content: trimmed }];
    setMessages(nextMessages);
    setQuestion("");
    try {
      const response = await sendChat(trimmed, language, location.trim(), sessionId);
      setSessionId(response.session_id);
      const completed = [...nextMessages, messageFromResponse(response)];
      setMessages(completed);
      persistConversation(response.session_id, completed);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not contact the assistant.");
    } finally {
      setBusy(false);
    }
  }

  async function submitVoice(file: File | Blob) {
    setError("");
    setBusy(true);
    try {
      const response = await sendVoice(file, language, location.trim(), sessionId);
      setSessionId(response.session_id);
      const userMessage: Message = {
        role: "user",
        content: response.transcript ?? "Voice message",
      };
      const completed = [...messages, userMessage, messageFromResponse(response)];
      setMessages(completed);
      persistConversation(response.session_id, completed);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Voice processing failed.");
    } finally {
      setBusy(false);
    }
  }

  async function startRecording() {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      audioChunks.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size) audioChunks.current.push(event.data);
      };
      recorder.onstop = () => {
        const audio = new Blob(audioChunks.current, { type: recorder.mimeType || "audio/webm" });
        stream.getTracks().forEach((track) => track.stop());
        void submitVoice(audio);
      };
      mediaRecorder.current = recorder;
      recorder.start();
      setRecording(true);
    } catch {
      setError("Microphone access is unavailable. Check your browser permission or upload an audio file.");
    }
  }

  function stopRecording() {
    mediaRecorder.current?.stop();
    setRecording(false);
  }

  function startNewChat() {
    setSessionId(null);
    setMessages([]);
    localStorage.removeItem(CURRENT_KEY);
    setError("");
  }

  async function openConversation(id: string) {
    setError("");
    try {
      const result = await getHistory(id);
      setSessionId(id);
      setLanguage(result.language);
      setMessages(result.messages.map((message) => ({
        role: message.role,
        content: message.content,
        verification: message.verification as Message["verification"],
        sources: message.sources,
      })));
      localStorage.setItem(CURRENT_KEY, id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not open conversation.");
    }
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!documentFile || !documentSource.trim()) return;
    const form = event.currentTarget;
    setError("");
    try {
      await uploadDocument(documentFile, {
        source: documentSource.trim(),
        language: documentLanguage,
        published_at: documentDate,
        crop: documentCrop.trim(),
        region: documentRegion.trim(),
      }, adminToken.trim());
      setDocumentFile(null);
      setDocumentSource("");
      setDocumentLanguage("unknown");
      setDocumentDate("");
      setDocumentCrop("");
      setDocumentRegion("");
      form.reset();
      setDocuments(await getDocuments());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Document upload failed.");
    }
  }

  async function handleApprove(id: string) {
    setError("");
    try {
      await approveDocument(id, adminToken.trim());
      setDocuments(await getDocuments());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not approve document.");
    }
  }

  async function handleEvaluation() {
    setBusy(true);
    setError("");
    try {
      setEvaluation(await runEvaluation());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Evaluation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSpeak(index: number) {
    const message = messages[index];
    if (!message || message.role !== "assistant") return;
    setError("");
    try {
      const audio = await synthesizeSpeech(message.content);
      setMessages((previous) => previous.map((item, current) =>
        current === index ? { ...item, ...audio } : item,
      ));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not generate audio.");
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">कृ</div>
          <div><strong>{chatLabel}</strong><span>किसान सहायता</span></div>
        </div>
        <button className="new-chat" onClick={startNewChat}>＋ New conversation</button>
        <p className="side-label">RECENT CHATS</p>
        <nav className="history-list" aria-label="Recent conversations">
          {history.map((item) => (
            <button
              className={`history-item ${sessionId === item.id ? "selected" : ""}`}
              key={item.id}
              onClick={() => void openConversation(item.id)}
              title={item.label}
            >
              <span aria-hidden="true">◷</span>{item.label}
            </button>
          ))}
          {history.length === 0 && <p className="empty-side">Your conversations will appear here.</p>}
        </nav>
        <div className="side-bottom">
          <button className={activePanel === "admin" ? "nav-button active" : "nav-button"} onClick={() => setActivePanel("admin")}>▤ Knowledge documents</button>
          <button className={activePanel === "evaluation" ? "nav-button active" : "nav-button"} onClick={() => setActivePanel("evaluation")}>◉ Evaluation</button>
          <div className="side-status"><span className="status-dot" />{config?.mode === "live" ? "AI model configured" : "Demo mode"}</div>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div className="mobile-brand"><span className="brand-mark">कृ</span><strong>Krishi Mitra</strong></div>
          <nav className="panel-nav" aria-label="Main navigation">
            <button className={activePanel === "chat" ? "current" : ""} onClick={() => setActivePanel("chat")}>Chat</button>
            <button className={activePanel === "admin" ? "current" : ""} onClick={() => setActivePanel("admin")}>Documents</button>
            <button className={activePanel === "evaluation" ? "current" : ""} onClick={() => setActivePanel("evaluation")}>Evaluation</button>
          </nav>
          <div className="topbar-spacer" />
          <label className="location-field">
            <span aria-hidden="true">⌖</span>
            <input value={location} onChange={(event) => setLocation(event.target.value)} placeholder="Village or district" aria-label="Village or district" />
          </label>
          <label className="language-select">
            <span className="sr-only">Preferred language</span>
            <select value={language} onChange={(event) => setLanguage(event.target.value as Language)}>
              <option value="hi">हिन्दी</option>
              <option value="mr">मराठी</option>
            </select>
          </label>
        </header>

        {error && <div className="error-banner" role="alert">{error}<button onClick={() => setError("")} aria-label="Dismiss error">×</button></div>}

        {activePanel === "chat" && (
          <section className="chat-view">
            <div className="chat-content">
              {messages.length === 0 ? (
                <div className="welcome">
                  <div className="welcome-icon" aria-hidden="true">🌱</div>
                  <p className="eyebrow">YOUR FARMING COMPANION</p>
                  <h1>नमस्ते, किसान मित्र</h1>
                  <p className="welcome-copy">Ask in Hindi or Marathi. I’ll use approved sources, and tell you clearly when I can’t verify an answer.</p>
                  {config?.mode === "demo" && <div className="demo-notice">Demo mode is on. Sample content is not official agricultural advice.</div>}
                  <div className="suggestions">
                    <button onClick={() => void submitQuestion("क्या इस डेमो में कृषि सलाह आधिकारिक है?")}>Is demo advice official?</button>
                    <button onClick={() => void submitQuestion("आज सोयाबीन का मंडी भाव क्या है?")}>Check today's mandi price</button>
                    <button onClick={() => void submitQuestion("सोयाबीन पर कौन सा कीटनाशक छिड़कूं?")}>Ask a crop safety question</button>
                  </div>
                </div>
              ) : (
                <div className="messages">
                  {messages.map((message, index) => (
                    <article className={`message ${message.role}`} key={`${index}-${message.content.slice(0, 12)}`}>
                      {message.role === "assistant" && <div className="assistant-avatar">कृ</div>}
                      <div className="message-body">
                        {message.role === "assistant" && (
                          <div className="answer-meta">
                            <span className={`badge ${message.verification ?? "unavailable"}`}>{verificationLabel(message.verification)}</span>
                          </div>
                        )}
                        <div className="bubble">{message.content}</div>
                        {message.transcript && <p className="transcript">Recognized speech: {message.transcript}</p>}
                        {message.sources && message.sources.length > 0 && (
                          <div className="sources">
                            <strong>Sources</strong>
                            {message.sources.map((source) => (
                              <div className="source-card" key={source.document_id}>
                                <span className="source-icon" aria-hidden="true">▤</span>
                                <span><b>{source.title}</b><small>{source.source} · {source.reference}{source.published_at ? ` · ${source.published_at}` : ""}{source.is_demo ? " · DEMO ONLY" : ""}</small></span>
                              </div>
                            ))}
                          </div>
                        )}
                        {message.role === "assistant" && config?.speech_synthesis_configured && !message.audio_base64 && (
                          <button className="listen-button" onClick={() => void handleSpeak(index)}>▶ Listen</button>
                        )}
                        {message.audio_base64 && message.audio_mime && (
                          <audio controls src={`data:${message.audio_mime};base64,${message.audio_base64}`} />
                        )}
                      </div>
                    </article>
                  ))}
                  {busy && <div className="thinking"><span /><span /><span /> Checking sources…</div>}
                  <div ref={historyEnd} />
                </div>
              )}
            </div>
            <form className="composer" onSubmit={(event) => { event.preventDefault(); void submitQuestion(); }}>
              <div className="composer-box">
                <textarea
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      void submitQuestion();
                    }
                  }}
                  placeholder={language === "hi" ? "अपना सवाल यहाँ लिखें…" : "तुमचा प्रश्न इथे लिहा…"}
                  rows={2}
                  disabled={busy}
                  aria-label="Your question"
                />
                <div className="composer-actions">
                  <div className="voice-actions">
                    {recording ? (
                      <button type="button" className="voice-button recording" onClick={stopRecording}>■ Stop & send</button>
                    ) : (
                      <button type="button" className="voice-button" disabled={busy || !config?.speech_recognition_configured} onClick={() => void startRecording()} title={config?.speech_recognition_configured ? "Record a voice question" : "Configure TRANSCRIPTION_MODEL_ID to enable speech recognition"}>🎙 Record</button>
                    )}
                    <label className="upload-audio" title="Upload audio question">
                      ⇧ Audio
                      <input type="file" accept="audio/*" disabled={busy || !config?.speech_recognition_configured} onChange={(event) => {
                        const file = event.target.files?.[0];
                        if (file) void submitVoice(file);
                        event.currentTarget.value = "";
                      }} />
                    </label>
                  </div>
                  <button className="send-button" type="submit" disabled={busy || !question.trim()} aria-label="Send message">↑</button>
                </div>
              </div>
              <p className="disclaimer">Agricultural information can affect your livelihood. Verify important decisions with a KVK or qualified expert.</p>
            </form>
          </section>
        )}

        {activePanel === "admin" && (
          <section className="utility-view">
            <div className="utility-heading"><p className="eyebrow">KNOWLEDGE MANAGEMENT</p><h1>Documents</h1><p>Only documents you explicitly approve are eligible for factual answers.</p></div>
            <div className="admin-card">
              <h2>Add a source document</h2>
              <p>Upload a UTF-8 text, Markdown, or PDF file. Documents start pending review.</p>
              {config?.admin_auth_required && (
                <label className="form-field">Admin token
                  <input type="password" value={adminToken} onChange={(event) => {
                    setAdminToken(event.target.value);
                    localStorage.setItem("krishi-admin-token", event.target.value);
                  }} autoComplete="off" />
                </label>
              )}
              <form className="upload-form" onSubmit={(event) => void handleUpload(event)}>
                <label className="form-field">Source / publisher
                  <input value={documentSource} onChange={(event) => setDocumentSource(event.target.value)} placeholder="ICAR, State Agricultural University, KVK…" required />
                </label>
                <label className="form-field">Document language
                  <select value={documentLanguage} onChange={(event) => setDocumentLanguage(event.target.value)}>
                    <option value="unknown">Unknown</option><option value="hi">Hindi</option><option value="mr">Marathi</option><option value="en">English</option>
                  </select>
                </label>
                <label className="form-field">Publication date
                  <input value={documentDate} onChange={(event) => setDocumentDate(event.target.value)} placeholder="YYYY-MM-DD" />
                </label>
                <label className="form-field">Crop
                  <input value={documentCrop} onChange={(event) => setDocumentCrop(event.target.value)} placeholder="Optional" />
                </label>
                <label className="form-field">Region
                  <input value={documentRegion} onChange={(event) => setDocumentRegion(event.target.value)} placeholder="Optional" />
                </label>
                <label className="file-picker">Choose document
                  <input type="file" accept=".txt,.md,.pdf" onChange={(event) => setDocumentFile(event.target.files?.[0] ?? null)} required />
                </label>
                <button className="primary-button" disabled={busy || !documentFile}>Upload for review</button>
              </form>
              {!config?.admin_auth_required && <p className="warning-note">Admin token is not configured; document actions are open for local development. Set ADMIN_TOKEN before deployment.</p>}
            </div>
            <div className="document-list">
              <div className="section-title"><h2>Knowledge base</h2><button className="text-button" onClick={() => void getDocuments().then(setDocuments)}>Refresh</button></div>
              {documents.length === 0 && <div className="empty-card">No documents uploaded yet.</div>}
              {documents.map((document) => (
                <article className="document-row" key={document.id}>
                  <div className="document-symbol">▤</div>
                  <div className="document-details">
                    <strong>{document.title}{document.is_demo && <span className="demo-tag">DEMO</span>}</strong>
                    <span>{document.source} · {document.filename} · {document.chunk_count} chunks</span>
                    <span>{[document.crop, document.region, document.language, document.published_at].filter(Boolean).join(" · ") || "No extra metadata"}</span>
                  </div>
                  {document.approved ? <span className="approval approved">Approved</span> : <button className="approve-button" onClick={() => void handleApprove(document.id)}>Approve</button>}
                </article>
              ))}
            </div>
          </section>
        )}

        {activePanel === "evaluation" && (
          <section className="utility-view">
            <div className="utility-heading"><p className="eyebrow">QUALITY & SAFETY</p><h1>Evaluation</h1><p>Run a small local retrieval and refusal check using the included sample cases.</p></div>
            <div className="admin-card evaluation-card">
              <h2>Local evaluation suite</h2>
              <p>Measures retrieval Recall@5 and refusal behavior on the bundled test set. It is not a real-farmer study and does not measure model faithfulness.</p>
              <button className="primary-button" onClick={() => void handleEvaluation()} disabled={busy}>{busy ? "Running…" : "Run evaluation"}</button>
            </div>
            {evaluation && (
              <div className="evaluation-results">
                {Object.entries(evaluation).map(([key, value]) => (
                  <div className="metric-card" key={key}><span>{key.replaceAll("_", " ")}</span><strong>{typeof value === "object" ? JSON.stringify(value) : String(value)}</strong></div>
                ))}
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}
