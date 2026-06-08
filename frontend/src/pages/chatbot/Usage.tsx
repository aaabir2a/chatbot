import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { ApiError, type Usage } from "../../api/types";
import {
  Card,
  EmptyState,
  ErrorState,
  Spinner,
} from "../../components/ui";
import { useBot } from "./ChatbotLayout";

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="stat">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

export default function UsagePage() {
  const { bot } = useBot();
  const [usage, setUsage] = useState<Usage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    api
      .usage(bot.id)
      .then(setUsage)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  };
  useEffect(load, [bot.id]);

  if (loading) return <Spinner />;
  if (error || !usage) return <ErrorState message={error ?? "No data"} onRetry={load} />;

  return (
    <>
      <div className="stats-row">
        <Stat label="Total messages" value={usage.total_messages} />
        <Stat label="Sessions" value={usage.total_sessions} />
        <Stat label="Prompt tokens" value={usage.prompt_tokens.toLocaleString()} />
        <Stat label="Completion tokens" value={usage.completion_tokens.toLocaleString()} />
        <Stat label="Total tokens" value={usage.total_tokens.toLocaleString()} />
      </div>

      <Card title="Recent conversations">
        {usage.recent.length === 0 ? (
          <EmptyState title="No conversations yet" hint="Use Test Chat or the API to start." />
        ) : (
          <div className="convo-list">
            {usage.recent.map((c, i) => (
              <div key={i} className="convo">
                <div className="convo-head">
                  <span className="mono muted">{c.session_id}</span>
                  <span className="muted">
                    {new Date(c.created_at).toLocaleString()} · {c.total_tokens} tok
                  </span>
                </div>
                <div className="convo-msg user">
                  <strong>User</strong> {c.user_message}
                </div>
                <div className="convo-msg bot">
                  <strong>Bot</strong> {c.assistant_message}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}
