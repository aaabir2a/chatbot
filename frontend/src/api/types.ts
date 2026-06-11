// Mirrors the backend Pydantic schemas.

export interface Org {
  id: string;
  name: string;
  email: string | null;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  org: Org;
}

export interface Chatbot {
  id: string;
  org_id: string;
  name: string;
  system_prompt: string;
  tone: string;
  welcome_message: string;
  model: string;
  lead_enabled: boolean;
  lead_after_messages: number;
  created_at: string;
}

export interface ChatbotInput {
  name?: string;
  system_prompt?: string;
  tone?: string;
  welcome_message?: string;
  model?: string;
  lead_enabled?: boolean;
  lead_after_messages?: number;
}

export interface Lead {
  id: string;
  chatbot_id: string;
  conversation_id: string | null;
  name: string;
  phone: string;
  email: string | null;
  status: "new" | "contacted";
  created_at: string;
}

export interface ApiKeyInfo {
  id: string;
  chatbot_id: string;
  name: string;
  prefix: string;
  revoked: boolean;
  created_at: string;
  last_used_at: string | null;
}

export interface ApiKeyCreated extends ApiKeyInfo {
  api_key: string; // plaintext, returned once
}

export type DocStatus = "processing" | "done" | "failed";

export interface DocumentInfo {
  id: string;
  filename: string;
  chunk_count: number;
  status: DocStatus;
  error: string | null;
  created_at: string;
}

export interface DocumentList {
  documents: DocumentInfo[];
  count: number;
}

export interface RecentConversation {
  session_id: string;
  user_message: string;
  assistant_message: string;
  total_tokens: number;
  created_at: string;
}

export interface Usage {
  chatbot_id: string;
  total_messages: number;
  total_sessions: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  recent: RecentConversation[];
}

export type ConvMode = "ai" | "human";
export type Sender = "visitor" | "ai" | "agent" | "system";

export interface Conversation {
  id: string;
  chatbot_id: string;
  chatbot_name: string;
  session_id: string;
  mode: ConvMode;
  waiting_for_human: boolean;
  assigned_agent_id: string | null;
  assigned_agent_name: string | null;
  unread: number;
  last_message: string;
  last_sender: Sender | null;
  last_message_at: string | null;
}

export interface ConvMessage {
  id: number;
  sender: Sender;
  content: string;
  agent_name: string | null;
  created_at: string | null;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}
