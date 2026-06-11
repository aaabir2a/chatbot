import { WIDGET_CSS } from "./styles";
import type { ChatWidgetInstance, ChatWidgetOptions } from "./types";
import { connectChatSocket, type ChatSocket, type WireMessage } from "./ws";

interface Msg {
  role: "user" | "bot" | "agent" | "system";
  text: string;
  name?: string;
}

function uid(): string {
  return Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
}

const ROLE_OF: Record<string, Msg["role"]> = {
  visitor: "user",
  ai: "bot",
  agent: "agent",
  system: "system",
};

/**
 * Create and mount a self-contained chat widget. Talks to the backend over a
 * WebSocket: AI replies stream token-by-token, and a live agent can take over.
 */
export function createChatWidget(opts: ChatWidgetOptions): ChatWidgetInstance {
  const theme = opts.theme ?? {};
  const target = opts.target ?? document.body;
  const position = theme.position ?? "bottom-right";
  const storeKey = `ragchat:${opts.chatbotId}`;

  // Persist only the session id (server holds the transcript).
  let sessionId: string;
  try {
    sessionId = JSON.parse(localStorage.getItem(storeKey) || "null")?.sessionId || uid();
  } catch {
    sessionId = uid();
  }
  try {
    localStorage.setItem(storeKey, JSON.stringify({ sessionId }));
  } catch {
    /* ignore */
  }

  let messages: Msg[] = [];
  let mode: "ai" | "human" = "ai";
  let agentName: string | null = null;
  let socket: ChatSocket | null = null;

  // ── Shadow host (style isolation both ways) ──
  const host = document.createElement("div");
  host.setAttribute("data-ragchat", opts.chatbotId);
  const shadow = host.attachShadow({ mode: "open" });
  const style = document.createElement("style");
  style.textContent = WIDGET_CSS;
  shadow.appendChild(style);

  const root = document.createElement("div");
  root.className = `rc-root rc-pos-${position === "bottom-left" ? "left" : "right"}`;
  if (theme.primaryColor) root.style.setProperty("--rc-primary", theme.primaryColor);
  if (theme.textOnPrimary) root.style.setProperty("--rc-on-primary", theme.textOnPrimary);
  if (theme.zIndex != null) root.style.setProperty("--rc-z", String(theme.zIndex));
  shadow.appendChild(root);

  // ── Launcher ──
  const launcher = document.createElement("button");
  launcher.className = "rc-launcher";
  launcher.setAttribute("aria-label", "Open chat");
  launcher.textContent = theme.launcherIcon ?? "💬";
  root.appendChild(launcher);

  // ── Panel ──
  const panel = document.createElement("div");
  panel.className = "rc-panel rc-hidden";
  panel.setAttribute("role", "dialog");
  panel.innerHTML = `
    <div class="rc-header">
      <div class="rc-header-text">
        <div class="rc-title"></div>
        <div class="rc-subtitle"></div>
      </div>
      <button class="rc-head-btn rc-human" title="Talk to a human" aria-label="Talk to a human">🧑‍💼</button>
      <button class="rc-head-btn rc-close" title="Close" aria-label="Close">×</button>
    </div>
    <div class="rc-banner rc-hidden"></div>
    <div class="rc-messages"></div>
    <form class="rc-composer">
      <textarea class="rc-input" rows="1"></textarea>
      <button type="submit" class="rc-send" aria-label="Send">➤</button>
    </form>
    <div class="rc-footer">Powered by RAG Console</div>
  `;
  root.appendChild(panel);

  const $ = <T extends Element>(sel: string) => panel.querySelector(sel) as T;
  ($(".rc-title") as HTMLElement).textContent = theme.title ?? "Assistant";
  ($(".rc-subtitle") as HTMLElement).textContent = theme.subtitle ?? "Ask me anything";
  const messagesEl = $(".rc-messages") as HTMLElement;
  const bannerEl = $(".rc-banner") as HTMLElement;
  const form = $(".rc-composer") as HTMLFormElement;
  const input = $(".rc-input") as HTMLTextAreaElement;
  const humanBtn = $(".rc-human") as HTMLButtonElement;
  input.placeholder = theme.placeholder ?? "Type your message…";

  let typingEl: HTMLElement | null = null;
  let streamingBot: { msg: Msg; el: HTMLElement } | null = null;

  // ── Rendering ──
  const scrollDown = () => {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  };

  const nodeFor = (m: Msg): HTMLElement => {
    if (m.role === "system") {
      const sys = document.createElement("div");
      sys.className = "rc-sys";
      sys.textContent = m.text;
      return sys;
    }
    const row = document.createElement("div");
    row.className = `rc-row ${m.role === "user" ? "user" : "bot"}`;
    const b = document.createElement("div");
    b.className = `rc-bubble ${m.role}`;
    if (m.role === "agent" && m.name) {
      const meta = document.createElement("div");
      meta.className = "rc-bubble-meta";
      meta.textContent = m.name;
      b.appendChild(meta);
    }
    b.appendChild(document.createTextNode(m.text));
    row.appendChild(b);
    return row;
  };

  const renderAll = () => {
    messagesEl.innerHTML = "";
    const list =
      messages.length === 0 && theme.welcomeMessage
        ? [{ role: "bot", text: theme.welcomeMessage } as Msg]
        : messages;
    for (const m of list) messagesEl.appendChild(nodeFor(m));
    scrollDown();
  };

  const appendMsg = (m: Msg) => {
    messages.push(m);
    messagesEl.appendChild(nodeFor(m));
    scrollDown();
  };

  const showTyping = () => {
    if (typingEl) return;
    const row = document.createElement("div");
    row.className = "rc-row bot";
    row.innerHTML = `<div class="rc-bubble bot"><span class="rc-typing"><span></span><span></span><span></span></span></div>`;
    messagesEl.appendChild(row);
    typingEl = row;
    scrollDown();
  };
  const clearTyping = () => {
    typingEl?.remove();
    typingEl = null;
  };

  const setBanner = (text: string | null) => {
    if (!text) {
      bannerEl.classList.add("rc-hidden");
      bannerEl.textContent = "";
    } else {
      bannerEl.classList.remove("rc-hidden");
      bannerEl.textContent = text;
    }
  };

  const applyMode = (newMode: string, name?: string | null) => {
    mode = newMode === "human" ? "human" : "ai";
    agentName = name ?? agentName;
    if (mode === "human") {
      setBanner(`🟢 You're chatting with ${agentName || "a team member"}`);
      humanBtn.classList.add("rc-hidden");
    } else {
      setBanner(null);
      humanBtn.classList.remove("rc-hidden");
    }
  };

  let leadFormEl: HTMLElement | null = null;
  const removeLeadForm = () => {
    leadFormEl?.remove();
    leadFormEl = null;
  };

  const renderLeadForm = (title: string, subtitle: string) => {
    if (leadFormEl) return; // only one at a time
    const wrap = document.createElement("div");
    wrap.className = "rc-lead";
    wrap.innerHTML = `
      <div class="rc-lead-title"></div>
      <div class="rc-lead-sub"></div>
      <input class="rc-lead-input rc-lead-name" type="text" placeholder="Your name" />
      <input class="rc-lead-input rc-lead-phone" type="tel" placeholder="Phone number" />
      <input class="rc-lead-input rc-lead-email" type="email" placeholder="Email" />
      <div class="rc-lead-actions">
        <button type="button" class="rc-lead-skip">No thanks</button>
        <button type="button" class="rc-lead-submit">Request callback</button>
      </div>
    `;
    (wrap.querySelector(".rc-lead-title") as HTMLElement).textContent = title;
    (wrap.querySelector(".rc-lead-sub") as HTMLElement).textContent = subtitle;
    const nameI = wrap.querySelector(".rc-lead-name") as HTMLInputElement;
    const phoneI = wrap.querySelector(".rc-lead-phone") as HTMLInputElement;
    const emailI = wrap.querySelector(".rc-lead-email") as HTMLInputElement;
    const submit = wrap.querySelector(".rc-lead-submit") as HTMLButtonElement;
    const skip = wrap.querySelector(".rc-lead-skip") as HTMLButtonElement;

    submit.addEventListener("click", () => {
      const name = nameI.value.trim();
      const phone = phoneI.value.trim();
      const email = emailI.value.trim();
      if (!name || phone.replace(/\D/g, "").length < 6) {
        wrap.classList.add("rc-lead-error");
        return;
      }
      if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        wrap.classList.add("rc-lead-error");
        return;
      }
      socket?.sendLead(name, phone, email);
      removeLeadForm();
    });
    skip.addEventListener("click", () => {
      // Tell the server so it can re-offer the form after a few more messages.
      socket?.sendLeadSkip();
      removeLeadForm();
    });

    messagesEl.appendChild(wrap);
    leadFormEl = wrap;
    scrollDown();
  };

  // ── Socket ──
  const buildHandlers = () => ({
    onStatus: () => {},
    onHistory: (wire: WireMessage[], m: string, name?: string | null) => {
      messages = wire.map((w) => ({
        role: ROLE_OF[w.sender] || "bot",
        text: w.content,
        name: w.agent_name || undefined,
      }));
      // renderAll wipes the DOM — drop refs to removed nodes, otherwise the
      // typing indicator can never be shown again after a reconnect.
      typingEl = null;
      streamingBot = null;
      leadFormEl = null;
      applyMode(m, name);
      renderAll();
    },
    onToken: (t: string) => {
      clearTyping();
      if (!streamingBot) {
        const msg: Msg = { role: "bot", text: "" };
        messages.push(msg);
        const row = nodeFor(msg);
        messagesEl.appendChild(row);
        streamingBot = { msg, el: row.querySelector(".rc-bubble") as HTMLElement };
      }
      streamingBot.msg.text += t;
      streamingBot.el.textContent = streamingBot.msg.text;
      scrollDown();
    },
    onAiDone: () => {
      clearTyping();
      streamingBot = null;
    },
    onAgentMessage: (text: string, name: string) => {
      clearTyping();
      appendMsg({ role: "agent", text, name });
    },
    onMode: (m: string, text?: string, name?: string) => {
      applyMode(m, name);
      if (text) appendMsg({ role: "system", text });
    },
    onSystem: (text: string) => appendMsg({ role: "system", text }),
    onLeadForm: (title: string, subtitle: string) => renderLeadForm(title, subtitle),
    onLeadSaved: (text: string) => {
      removeLeadForm();
      appendMsg({ role: "system", text });
    },
  });

  socket = connectChatSocket(opts.apiUrl, opts.apiKey, sessionId, buildHandlers());

  // ── Send flow ──
  const send = () => {
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    input.style.height = "auto";
    appendMsg({ role: "user", text });
    if (mode === "ai") showTyping(); // agent replies have no typing indicator
    socket?.send(text);
  };

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    send();
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });
  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 96) + "px";
  });

  humanBtn.addEventListener("click", () => {
    socket?.requestHuman();
    appendMsg({ role: "system", text: "Requesting a human agent…" });
  });

  let isOpen = false;
  const open = () => {
    isOpen = true;
    panel.classList.remove("rc-hidden");
    launcher.classList.add("rc-hidden");
    renderAll();
    setTimeout(() => input.focus(), 50);
  };
  const close = () => {
    isOpen = false;
    panel.classList.add("rc-hidden");
    launcher.classList.remove("rc-hidden");
  };
  const toggle = () => (isOpen ? close() : open());
  const reset = () => {
    sessionId = uid();
    try {
      localStorage.setItem(storeKey, JSON.stringify({ sessionId }));
    } catch {
      /* ignore */
    }
    messages = [];
    streamingBot = null;
    leadFormEl = null;
    renderAll();
    // Reconnect with the new session id (reuse the same handlers).
    socket?.close();
    socket = connectChatSocket(opts.apiUrl, opts.apiKey, sessionId, buildHandlers());
  };

  launcher.addEventListener("click", open);
  ($(".rc-close") as HTMLElement).addEventListener("click", close);

  target.appendChild(host);
  renderAll();

  return {
    open,
    close,
    toggle,
    reset,
    destroy: () => {
      socket?.close();
      host.remove();
    },
  };
}
