import { useEffect, useRef, useState } from "react";
import { streamTestChat } from "../../api/client";
import { Button, Card, Input } from "../../components/ui";
import { useBot } from "./ChatbotLayout";

interface Msg {
  role: "user" | "bot";
  text: string;
}

export default function TestChatPage() {
  const { bot } = useBot();
  const [sessionId] = useState(() => `test-${Math.random().toString(36).slice(2, 9)}`);
  const [messages, setMessages] = useState<Msg[]>([
    { role: "bot", text: bot.welcome_message },
  ]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    const text = input.trim();
    if (!text || streaming) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text }, { role: "bot", text: "" }]);
    setStreaming(true);

    const appendToBot = (chunk: string) =>
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = {
          role: "bot",
          text: copy[copy.length - 1].text + chunk,
        };
        return copy;
      });

    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      setStreaming(false);
    };

    try {
      await streamTestChat(bot.id, text, sessionId, {
        onToken: appendToBot,
        onDone: finish,
        onError: (e) => {
          appendToBot(`\n[error: ${e}]`);
          finish();
        },
      });
    } catch (e) {
      appendToBot(`\n[error: ${e instanceof Error ? e.message : "failed"}]`);
      finish();
    }
  };

  return (
    <Card title={`Test Chat · ${bot.name}`}>
      <div className="chat-box">
        <div className="chat-scroll">
          {messages.map((m, i) => (
            <div key={i} className={`bubble-row ${m.role}`}>
              <div className={`bubble ${m.role}`}>
                {m.text || <span className="typing">▋</span>}
              </div>
            </div>
          ))}
          <div ref={endRef} />
        </div>
        <form
          className="chat-input"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask something grounded in this chatbot's documents…"
            disabled={streaming}
          />
          <Button type="submit" loading={streaming}>
            Send
          </Button>
        </form>
      </div>
      <p className="muted small">
        Session: <span className="mono">{sessionId}</span>. Answers use only this
        chatbot's ingested documents.
      </p>
    </Card>
  );
}
