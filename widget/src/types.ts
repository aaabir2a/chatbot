// Public API surface. ONLY these options are exposed to consumers — no internal
// backend config (models, prompts, db, etc.) ever leaves the server.

export interface ChatTheme {
  /** Primary brand color (header, launcher, user bubbles). Default #5b5bf5. */
  primaryColor?: string;
  /** Text/icon color shown on the primary color. Default #ffffff. */
  textOnPrimary?: string;
  /** Corner to anchor the launcher + panel. Default "bottom-right". */
  position?: "bottom-right" | "bottom-left";
  /** Header title. Default "Assistant". */
  title?: string;
  /** Header subtitle. Default "Ask me anything". */
  subtitle?: string;
  /** First bot message shown when the chat is empty. */
  welcomeMessage?: string;
  /** Input placeholder text. */
  placeholder?: string;
  /** Pre-set questions shown as clickable chips when the chat is empty.
   *  Clicking one sends it immediately. Keep to 2–4 short items. */
  suggestedQuestions?: string[];
  /** Launcher glyph (emoji or text). Default "💬". */
  launcherIcon?: string;
  /** Stack order for the floating elements. Default 2147483000. */
  zIndex?: number;
}

export interface ChatWidgetOptions {
  /** Base URL of the chatbot backend, e.g. "https://api.example.com". */
  apiUrl: string;
  /** Per-chatbot API key (sent as X-API-Key). */
  apiKey: string;
  /** Chatbot id — namespaces session/history storage in the browser. */
  chatbotId: string;
  /** Visual customization. */
  theme?: ChatTheme;
  /** Where to mount. Defaults to document.body. */
  target?: HTMLElement;
}

export interface ChatWidgetInstance {
  open: () => void;
  close: () => void;
  toggle: () => void;
  /** Clear persisted conversation + start a fresh session. */
  reset: () => void;
  /** Remove the widget from the DOM. */
  destroy: () => void;
}

export type StreamHandlers = {
  onToken: (t: string) => void;
  onDone: () => void;
  onError: (message: string) => void;
};
