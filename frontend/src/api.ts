import type {
  AppConfig,
  ChatResponse,
  DocumentItem,
  Language,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json() as { detail?: string };
      message = body.detail ?? message;
    } catch {
      // Keep the HTTP status when the server does not return JSON.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export function getConfig(): Promise<AppConfig> {
  return request<AppConfig>("/api/config");
}

export function sendChat(
  question: string,
  language: Language,
  location: string,
  sessionId: string | null,
): Promise<ChatResponse> {
  return request<ChatResponse>("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, language, location: location || null, session_id: sessionId }),
  });
}

export function sendVoice(
  file: File | Blob,
  language: Language,
  location: string,
  sessionId: string | null,
): Promise<ChatResponse> {
  const form = new FormData();
  form.append("file", file, file instanceof File ? file.name : "recording.webm");
  form.append("language", language);
  if (location) form.append("location", location);
  if (sessionId) form.append("session_id", sessionId);
  return request<ChatResponse>("/api/voice", { method: "POST", body: form });
}

export function getHistory(sessionId: string): Promise<{
  session_id: string;
  language: Language;
  messages: {
    role: "user" | "assistant";
    content: string;
    verification: string;
    sources?: import("./types").SourceReference[];
  }[];
}> {
  return request(`/api/sessions/${encodeURIComponent(sessionId)}`);
}

export function getDocuments(): Promise<DocumentItem[]> {
  return request<DocumentItem[]>("/api/documents");
}

export function uploadDocument(
  file: File,
  metadata: { source: string; language: string; published_at: string; crop: string; region: string },
  token: string,
): Promise<DocumentItem> {
  const form = new FormData();
  form.append("file", file);
  form.append("source", metadata.source);
  form.append("language", metadata.language);
  if (metadata.published_at) form.append("published_at", metadata.published_at);
  if (metadata.crop) form.append("crop", metadata.crop);
  if (metadata.region) form.append("region", metadata.region);
  return request<DocumentItem>("/api/documents/upload", {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: form,
  });
}

export function synthesizeSpeech(text: string): Promise<{ audio_base64: string; audio_mime: string }> {
  return request("/api/speech", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
}

export function approveDocument(id: string, token: string): Promise<DocumentItem> {
  return request<DocumentItem>(`/api/documents/${encodeURIComponent(id)}/approve`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
}

export function runEvaluation(): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>("/api/evaluation/run", { method: "POST" });
}
