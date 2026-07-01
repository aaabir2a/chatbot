import {
  ApiError,
  type ApiKeyCreated,
  type ApiKeyInfo,
  type Chatbot,
  type ChatbotInput,
  type Conversation,
  type ConvMessage,
  type CrmKeyCreated,
  type CrmKeyInfo,
  type Lead,
  type WebhookConfig,
  type DocumentList,
  type DocumentInfo,
  type Org,
  type TokenResponse,
  type Usage,
} from "./types";

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const TOKEN_KEY = "rag_token";

/** Public base URL of the backend (for embed snippets shown in the UI). */
export const apiBaseUrl = (): string => BASE.replace(/\/$/, "");

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

async function request<T>(
  path: string,
  opts: { method?: string; body?: unknown; auth?: boolean } = {},
): Promise<T> {
  const { method = "GET", body, auth = true } = opts;
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth) {
    const t = tokenStore.get();
    if (t) headers["Authorization"] = `Bearer ${t}`;
  }
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || JSON.stringify(data);
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

async function upload<T>(path: string, file: File): Promise<T> {
  const headers: Record<string, string> = {};
  const t = tokenStore.get();
  if (t) headers["Authorization"] = `Bearer ${t}`;
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}${path}`, { method: "POST", headers, body: form });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export const api = {
  // ── Auth ──
  signup: (name: string, email: string, password: string) =>
    request<TokenResponse>("/auth/signup", {
      method: "POST",
      body: { name, email, password },
      auth: false,
    }),
  login: (email: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: { email, password },
      auth: false,
    }),
  me: () => request<Org>("/auth/me"),

  // ── Chatbots ──
  listChatbots: () => request<Chatbot[]>("/chatbots"),
  createChatbot: (body: ChatbotInput) =>
    request<Chatbot>("/chatbots", { method: "POST", body }),
  getChatbot: (id: string) => request<Chatbot>(`/chatbots/${id}`),
  updateChatbot: (id: string, body: ChatbotInput) =>
    request<Chatbot>(`/chatbots/${id}`, { method: "PATCH", body }),
  deleteChatbot: (id: string) =>
    request<void>(`/chatbots/${id}`, { method: "DELETE" }),

  // ── API keys ──
  listKeys: (chatbotId: string) =>
    request<ApiKeyInfo[]>(`/chatbots/${chatbotId}/api-keys`),
  createKey: (chatbotId: string, name: string) =>
    request<ApiKeyCreated>(`/chatbots/${chatbotId}/api-keys`, {
      method: "POST",
      body: { name },
    }),
  revokeKey: (keyId: string) =>
    request<{ id: string; revoked: boolean }>(`/api-keys/${keyId}`, {
      method: "DELETE",
    }),

  // ── Documents ──
  listDocs: (chatbotId: string) =>
    request<DocumentList>(`/chatbots/${chatbotId}/documents`),
  uploadDoc: (chatbotId: string, file: File) =>
    upload<DocumentInfo>(`/chatbots/${chatbotId}/documents`, file),
  deleteDoc: (chatbotId: string, docId: string) =>
    request<unknown>(`/chatbots/${chatbotId}/documents/${docId}`, {
      method: "DELETE",
    }),

  // ── Usage ──
  usage: (chatbotId: string) => request<Usage>(`/chatbots/${chatbotId}/usage`),

  // ── Leads ──
  listLeads: (chatbotId?: string) =>
    request<Lead[]>(
      chatbotId ? `/leads?chatbot_id=${chatbotId}` : "/leads",
    ),
  updateLead: (leadId: string, status: "new" | "contacted") =>
    request<Lead>(`/leads/${leadId}`, { method: "PATCH", body: { status } }),

  // ── Live chats ──
  listConversations: () =>
    request<{ conversations: Conversation[]; count: number }>("/conversations"),
  conversationMessages: (id: string) =>
    request<{ conversation: Conversation; messages: ConvMessage[] }>(
      `/conversations/${id}/messages`,
    ),

  // ── CRM integration keys ──
  listCrmKeys: () => request<CrmKeyInfo[]>("/crm-keys"),
  createCrmKey: (name: string) =>
    request<CrmKeyCreated>("/crm-keys", { method: "POST", body: { name } }),
  revokeCrmKey: (id: string) =>
    request<{ id: string; revoked: boolean }>(`/crm-keys/${id}`, { method: "DELETE" }),

  // ── Webhook ──
  getWebhook: () => request<WebhookConfig>("/webhook"),
  setWebhook: (url: string, enabled: boolean) =>
    request<WebhookConfig>("/webhook", { method: "PUT", body: { url, enabled } }),
  rotateWebhookSecret: () =>
    request<WebhookConfig>("/webhook/rotate-secret", { method: "POST" }),
  testWebhook: () => request<{ delivered: boolean }>("/webhook/test", { method: "POST" }),
};

/** WebSocket URL for the agent dashboard (JWT in query param). */
export function agentWsUrl(): string {
  const base = BASE.replace(/^http/, "ws").replace(/\/$/, "");
  return `${base}/ws/agent?token=${encodeURIComponent(tokenStore.get() ?? "")}`;
}

/**
 * Stream a test-chat response (SSE over fetch, so we can send the JWT header).
 */
export async function streamTestChat(
  chatbotId: string,
  message: string,
  sessionId: string,
  handlers: {
    onToken: (t: string) => void;
    onDone: () => void;
    onError: (e: string) => void;
  },
): Promise<void> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const t = tokenStore.get();
  if (t) headers["Authorization"] = `Bearer ${t}`;

  const res = await fetch(`${BASE}/chatbots/${chatbotId}/test-chat`, {
    method: "POST",
    headers,
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  if (!res.ok || !res.body) {
    handlers.onError(`Request failed (${res.status})`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let event = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (line.startsWith("event:")) {
        event = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        const data = JSON.parse(line.slice(5).trim());
        if (event === "token") handlers.onToken(data.token);
        else if (event === "done") handlers.onDone();
        else if (event === "error") handlers.onError(data.error);
      }
    }
  }
  handlers.onDone();
}
