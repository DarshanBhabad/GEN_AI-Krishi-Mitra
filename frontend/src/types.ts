export type Language = "hi" | "mr";
export type Verification = "verified" | "uncertain" | "unavailable" | "demo";

export interface SourceReference {
  document_id: string;
  title: string;
  source: string;
  reference: string;
  published_at: string | null;
  is_demo: boolean;
}

export interface ChatResponse {
  session_id: string;
  answer: string;
  verification: Verification;
  reason: string;
  intent: string;
  language: Language;
  sources: SourceReference[];
  live_data: Record<string, unknown> | null;
  transcript: string | null;
  audio_base64: string | null;
  audio_mime: string | null;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  verification?: Verification;
  sources?: SourceReference[];
  audio_base64?: string | null;
  audio_mime?: string | null;
  transcript?: string | null;
}

export interface SavedConversation {
  id: string;
  label: string;
  messages: Message[];
}

export interface DocumentItem {
  id: string;
  title: string;
  source: string;
  filename: string;
  language: string;
  published_at: string | null;
  crop: string | null;
  region: string | null;
  approved: boolean;
  is_demo: boolean;
  chunk_count: number;
}

export interface AppConfig {
  mode: "demo" | "live";
  chat_model_configured: boolean;
  embeddings_configured: boolean;
  speech_recognition_configured: boolean;
  speech_synthesis_configured: boolean;
  qdrant_configured: boolean;
  mandi_api_configured: boolean;
  weather_provider: string;
  supported_languages: string[];
  admin_auth_required: boolean;
}
