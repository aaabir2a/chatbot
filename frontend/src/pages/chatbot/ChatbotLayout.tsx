import { useEffect, useState } from "react";
import {
  NavLink,
  Outlet,
  useNavigate,
  useOutletContext,
  useParams,
} from "react-router-dom";
import { api } from "../../api/client";
import { ApiError, type Chatbot } from "../../api/types";
import { PageHeader } from "../../components/Layout";
import { ErrorState, Spinner } from "../../components/ui";

export interface BotCtx {
  bot: Chatbot;
  reload: () => void;
}

export function useBot(): BotCtx {
  return useOutletContext<BotCtx>();
}

const TABS = [
  { to: "config", label: "Configuration" },
  { to: "documents", label: "Documents" },
  { to: "keys", label: "API Keys" },
  { to: "usage", label: "Usage" },
  { to: "chat", label: "Test Chat" },
];

export default function ChatbotLayout() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [bot, setBot] = useState<Chatbot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    api
      .getChatbot(id)
      .then(setBot)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  };
  useEffect(load, [id]);

  if (loading) return <Spinner />;
  if (error || !bot) return <ErrorState message={error ?? "Not found"} onRetry={load} />;

  return (
    <>
      <PageHeader
        title={bot.name}
        subtitle={<span className="tag">{bot.model}</span>}
        back={
          <button className="back-link" onClick={() => navigate("/")}>
            ← All chatbots
          </button>
        }
      />
      <div className="tabs">
        {TABS.map((t) => (
          <NavLink key={t.to} to={t.to} className="tab">
            {t.label}
          </NavLink>
        ))}
      </div>
      <div className="tab-body">
        <Outlet context={{ bot, reload: load } satisfies BotCtx} />
      </div>
    </>
  );
}
