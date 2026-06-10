// WebSocket transport for live mode. Streams AI tokens AND relays live agent
// messages / mode changes. Falls back to auto-reconnect on drop.

export interface WireMessage {
  sender: "visitor" | "ai" | "agent" | "system";
  content: string;
  agent_name: string | null;
}

export interface ChatSocketHandlers {
  onHistory: (messages: WireMessage[], mode: string, agentName?: string | null) => void;
  onToken: (token: string) => void;
  onAiDone: () => void;
  onAgentMessage: (text: string, agentName: string) => void;
  onMode: (mode: string, text?: string, agentName?: string) => void;
  onSystem: (text: string) => void;
  onStatus: (connected: boolean) => void;
  onLeadForm: (title: string, subtitle: string) => void;
  onLeadSaved: (text: string) => void;
}

export interface ChatSocket {
  send: (text: string) => void;
  requestHuman: () => void;
  sendLead: (name: string, phone: string) => void;
  close: () => void;
}

export function connectChatSocket(
  apiUrl: string,
  apiKey: string,
  sessionId: string,
  handlers: ChatSocketHandlers,
): ChatSocket {
  const base = apiUrl.replace(/^http/, "ws").replace(/\/$/, "");
  const url = `${base}/ws/chat/${encodeURIComponent(sessionId)}?api_key=${encodeURIComponent(apiKey)}`;

  let ws: WebSocket | null = null;
  let closed = false;

  const open = () => {
    ws = new WebSocket(url);
    ws.onopen = () => handlers.onStatus(true);
    ws.onclose = () => {
      handlers.onStatus(false);
      if (!closed) setTimeout(open, 2000); // reconnect
    };
    ws.onmessage = (ev) => {
      let d: any;
      try {
        d = JSON.parse(ev.data);
      } catch {
        return;
      }
      switch (d.type) {
        case "history":
          handlers.onHistory(d.messages || [], d.mode || "ai", d.agent_name);
          break;
        case "token":
          handlers.onToken(d.token || "");
          break;
        case "ai_done":
          handlers.onAiDone();
          break;
        case "agent_message":
          handlers.onAgentMessage(d.text || "", d.agent_name || "Agent");
          break;
        case "mode":
          handlers.onMode(d.mode, d.text, d.agent_name);
          break;
        case "system":
          handlers.onSystem(d.text || "");
          break;
        case "lead_form":
          handlers.onLeadForm(d.title || "Want a callback?", d.subtitle || "");
          break;
        case "lead_saved":
          handlers.onLeadSaved(d.text || "Thank you!");
          break;
      }
    };
  };
  open();

  const safeSend = (obj: object) => {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
  };

  return {
    send: (text: string) => safeSend({ type: "message", text }),
    requestHuman: () => safeSend({ type: "request_human" }),
    sendLead: (name: string, phone: string) =>
      safeSend({ type: "lead", name, phone }),
    close: () => {
      closed = true;
      ws?.close();
    },
  };
}
