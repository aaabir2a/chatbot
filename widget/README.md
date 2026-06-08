# @rag/chat-widget

Embeddable chat widget for the RAG Console backend. One codebase, two ways to
ship it:

- **React component** — `<ChatWidget apiUrl apiKey chatbotId theme />`
- **Script embed** — one `<script>` tag for any plain-HTML (or non-React) site

Both render the *same* widget: a floating bubble that opens a chat panel,
streams responses token-by-token (SSE), shows a typing indicator, persists the
session per browser, and handles errors gracefully. Styles live in a **Shadow
DOM**, so the widget never leaks CSS into the host page and the host's CSS never
breaks the widget.

Only four things are public: `apiUrl`, `apiKey`, `chatbotId`, and `theme`. No
backend internals (models, prompts, vector store, etc.) are ever exposed.

---

## Build

```bash
cd widget
npm install
npm run build
```

Outputs to `dist/`:

| File | Use |
|---|---|
| `dist/rag-chat-widget.js` / `.cjs` | npm package (ESM / CJS), React is a peer dep |
| `dist/index.d.ts` | TypeScript types |
| `dist/widget.js` | self-contained IIFE for the `<script>` embed |

---

## Use in a React project (e.g. a Vercel site)

Install it (from a registry, a tarball via `npm pack`, or a path/workspace dep):

```bash
npm install @rag/chat-widget
```

```tsx
import { ChatWidget } from "@rag/chat-widget";

export default function App() {
  return (
    <>
      {/* ...your app... */}
      <ChatWidget
        apiUrl="https://api.your-domain.com"
        apiKey={import.meta.env.VITE_CHAT_API_KEY}
        chatbotId="your-chatbot-id"
        theme={{
          title: "Support",
          subtitle: "Ask about our product",
          primaryColor: "#5b5bf5",
          position: "bottom-right",
          welcomeMessage: "Hi! How can I help?",
        }}
      />
    </>
  );
}
```

The widget mounts itself into `<body>` (Shadow DOM isolated), so placement in
the tree doesn't matter and it won't clash with your styles.

---

## Use on a plain-HTML site (script embed)

Copy `dist/widget.js` to your site (or serve it from a CDN) and add one tag.
It auto-initializes from `data-*` attributes:

```html
<script
  src="https://cdn.your-domain.com/widget.js"
  data-api-url="https://api.your-domain.com"
  data-api-key="YOUR_API_KEY"
  data-chatbot-id="YOUR_CHATBOT_ID"
  data-title="Support"
  data-primary-color="#5b5bf5"
  data-position="bottom-right"
  data-welcome-message="Hi! Ask me anything.">
</script>
```

Prefer to control it yourself? Skip the `data-*` attrs and call the global:

```html
<script src="/widget.js"></script>
<script>
  const widget = window.RagChat.init({
    apiUrl: "https://api.your-domain.com",
    apiKey: "YOUR_API_KEY",
    chatbotId: "YOUR_CHATBOT_ID",
    theme: { title: "Support", primaryColor: "#5b5bf5" },
  });
  // widget.open() / widget.close() / widget.toggle() / widget.reset() / widget.destroy()
</script>
```

A working demo is in `demo/embed.html` (run `npm run build` first).

---

## Theme options

| Prop | Default | Notes |
|---|---|---|
| `primaryColor` | `#5b5bf5` | header, launcher, user bubbles |
| `textOnPrimary` | `#ffffff` | text/icon on the primary color |
| `position` | `bottom-right` | or `bottom-left` |
| `title` | `Assistant` | header title |
| `subtitle` | `Ask me anything` | header subtitle |
| `welcomeMessage` | — | shown when the chat is empty |
| `placeholder` | `Type your message…` | input placeholder |
| `launcherIcon` | `💬` | emoji/text on the bubble |
| `zIndex` | `2147483000` | stacking order |

Script embed: each maps to a kebab-case `data-*` attribute (e.g.
`primaryColor` → `data-primary-color`).

---

## How it talks to the backend

`POST {apiUrl}/chat` with header `X-API-Key: {apiKey}` and body
`{ message, session_id }`, consuming the SSE stream (`event: token | done |
error`). `session_id` is generated once and stored in `localStorage` under
`ragchat:{chatbotId}` along with the transcript, so reloads keep context. The
"new chat" (⟲) button starts a fresh session.

## Security note

A widget API key lives in the browser — that's unavoidable for a public,
client-side widget. Use a **dedicated per-chatbot key** (revocable from the
dashboard) and keep the backend's per-key rate limit on. The key only grants
`/chat` + `/ingest` for that single chatbot; it can't touch other tenants or
any management API.
```
