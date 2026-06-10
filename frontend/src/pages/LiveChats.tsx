import { useEffect, useRef, useState } from "react";
import { agentWsUrl, api } from "../api/client";
import type { Conversation, ConvMessage } from "../api/types";
import { PageHeader } from "../components/Layout";
import { useToast } from "../components/Toast";
import { Badge, Button, EmptyState, Spinner } from "../components/ui";

function relTime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function LiveChats() {
  const toast = useToast();
  const wsRef = useRef<WebSocket | null>(null);
  const agentIdRef = useRef<string>("");
  const selectedRef = useRef<string | null>(null);

  const [connected, setConnected] = useState(false);
  const [convs, setConvs] = useState<Record<string, Conversation>>({});
  const [order, setOrder] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConvMessage[]>([]);
  const [reply, setReply] = useState("");
  const [loadingMsgs, setLoadingMsgs] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  // ── helpers ──
  const upsertConv = (c: Conversation) =>
    setConvs((m) => {
      const next = { ...m, [c.id]: c };
      return next;
    });
  const bumpOrder = (id: string) =>
    setOrder((o) => [id, ...o.filter((x) => x !== id)]);

  const appendMsg = (cid: string, msg: ConvMessage) => {
    if (selectedRef.current !== cid) return;
    setMessages((ms) => (ms.some((x) => x.id === msg.id) ? ms : [...ms, msg]));
  };

  // ── initial load + websocket ──
  useEffect(() => {
    api
      .listConversations()
      .then((r) => {
        const map: Record<string, Conversation> = {};
        r.conversations.forEach((c) => (map[c.id] = c));
        setConvs(map);
        setOrder(r.conversations.map((c) => c.id));
      })
      .catch(() => {});

    const connect = () => {
      const ws = new WebSocket(agentWsUrl());
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        // simple reconnect
        setTimeout(() => {
          if (wsRef.current === ws) connect();
        }, 2000);
      };
      ws.onmessage = (ev) => {
        const data = JSON.parse(ev.data);
        switch (data.type) {
          case "inbox":
            agentIdRef.current = data.agent_id;
            break;
          case "lead":
          case "conversation_updated":
          case "message":
          case "mode": {
            if (data.type === "lead" && data.lead) {
              toast.success(`New lead: ${data.lead.name} (${data.lead.phone})`);
            }
            if (data.conversation) {
              upsertConv(data.conversation);
              bumpOrder(data.conversation.id);
            }
            if (data.message && data.conversation_id) {
              appendMsg(data.conversation_id, data.message);
            }
            if (data.type === "conversation_updated" && data.message && data.conversation) {
              appendMsg(data.conversation.id, data.message);
            }
            break;
          }
          case "history":
            if (data.conversation_id === selectedRef.current) {
              setMessages(data.messages);
              setLoadingMsgs(false);
            }
            if (data.conversation) upsertConv(data.conversation);
            break;
          case "error":
            toast.error(data.message || "Action failed");
            break;
        }
      };
    };
    connect();

    return () => {
      const ws = wsRef.current;
      wsRef.current = null;
      ws?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = (payload: object) => wsRef.current?.send(JSON.stringify(payload));

  const select = (id: string) => {
    setSelected(id);
    selectedRef.current = id;
    setMessages([]);
    setLoadingMsgs(true);
    // locally clear unread
    setConvs((m) => (m[id] ? { ...m, [id]: { ...m[id], unread: 0 } } : m));
    send({ type: "subscribe", conversation_id: id });
  };

  const takeOver = (id: string) => send({ type: "take_over", conversation_id: id });
  const release = (id: string) => send({ type: "release", conversation_id: id });
  const sendReply = () => {
    const text = reply.trim();
    if (!text || !selected) return;
    send({ type: "message", conversation_id: selected, text });
    setReply("");
  };

  const current = selected ? convs[selected] : null;
  const myId = agentIdRef.current;
  const list = order.map((id) => convs[id]).filter(Boolean);

  return (
    <>
      <PageHeader
        title="Live Chats"
        subtitle="Monitor conversations and take over from the AI in real time."
        actions={
          <Badge kind={connected ? "success" : "warn"}>
            {connected ? "● connected" : "● reconnecting"}
          </Badge>
        }
      />

      <div className="inbox">
        {/* List */}
        <div className="inbox-list">
          {list.length === 0 ? (
            <EmptyState title="No conversations yet" hint="They appear here as visitors chat." />
          ) : (
            list.map((c) => (
              <button
                key={c.id}
                className={`inbox-item ${selected === c.id ? "active" : ""}`}
                onClick={() => select(c.id)}
              >
                <div className="inbox-item-top">
                  <span className="inbox-name">{c.chatbot_name}</span>
                  <span className="muted small">{relTime(c.last_message_at)}</span>
                </div>
                <div className="inbox-preview">
                  {c.last_sender === "visitor" ? "Visitor: " : ""}
                  {c.last_message || "—"}
                </div>
                <div className="inbox-tags">
                  {c.mode === "human" ? (
                    <Badge kind="success">human · {c.assigned_agent_name}</Badge>
                  ) : (
                    <Badge kind="warn">AI</Badge>
                  )}
                  {c.waiting_for_human && <Badge kind="danger">waiting</Badge>}
                  {c.unread > 0 && <span className="unread-dot">{c.unread}</span>}
                </div>
              </button>
            ))
          )}
        </div>

        {/* Conversation */}
        <div className="inbox-convo">
          {!current ? (
            <EmptyState title="Select a conversation" hint="Pick a chat on the left to view it." />
          ) : (
            <>
              <div className="convo-bar">
                <div>
                  <div className="convo-bar-title">{current.chatbot_name}</div>
                  <div className="muted small mono">{current.session_id}</div>
                </div>
                <div className="convo-bar-actions">
                  {current.mode === "human" ? (
                    <>
                      <Badge kind="success">
                        Handled by {current.assigned_agent_name}
                      </Badge>
                      <Button variant="secondary" onClick={() => release(current.id)}>
                        Hand back to AI
                      </Button>
                    </>
                  ) : (
                    <Button onClick={() => takeOver(current.id)}>Take over</Button>
                  )}
                </div>
              </div>

              <div className="convo-messages">
                {loadingMsgs ? (
                  <Spinner />
                ) : (
                  messages.map((m) => {
                    if (m.sender === "system") {
                      return (
                        <div key={m.id} className="sys-line">
                          {m.content}
                        </div>
                      );
                    }
                    const side = m.sender === "visitor" ? "left" : "right";
                    return (
                      <div key={m.id} className={`agent-row ${side}`}>
                        <div className={`agent-bubble ${m.sender}`}>
                          <div className="agent-bubble-meta">
                            {m.sender === "visitor"
                              ? "Visitor"
                              : m.sender === "ai"
                                ? "AI"
                                : m.agent_name || "Agent"}
                          </div>
                          {m.content}
                        </div>
                      </div>
                    );
                  })
                )}
                <div ref={endRef} />
              </div>

              <form
                className="convo-reply"
                onSubmit={(e) => {
                  e.preventDefault();
                  sendReply();
                }}
              >
                <input
                  className="input"
                  placeholder={
                    current.mode === "human"
                      ? "Type a reply to the visitor…"
                      : "Take over to reply as a human"
                  }
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                  disabled={
                    current.mode !== "human" ||
                    (!!current.assigned_agent_id && current.assigned_agent_id !== myId)
                  }
                />
                <Button
                  type="submit"
                  disabled={
                    current.mode !== "human" ||
                    (!!current.assigned_agent_id && current.assigned_agent_id !== myId)
                  }
                >
                  Send
                </Button>
              </form>
            </>
          )}
        </div>
      </div>
    </>
  );
}
