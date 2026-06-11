import { useEffect, useState } from "react";
import { api } from "../api/client";
import { ApiError, type Chatbot, type Lead } from "../api/types";
import { PageHeader } from "../components/Layout";
import { useToast } from "../components/Toast";
import { Badge, Button, Card, EmptyState, ErrorState, Spinner } from "../components/ui";

export default function Leads() {
  const toast = useToast();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [bots, setBots] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    Promise.all([api.listLeads(), api.listChatbots()])
      .then(([ls, cs]) => {
        setLeads(ls);
        setBots(Object.fromEntries(cs.map((c: Chatbot) => [c.id, c.name])));
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const toggle = async (lead: Lead) => {
    const next = lead.status === "new" ? "contacted" : "new";
    setBusy(lead.id);
    try {
      await api.updateLead(lead.id, next);
      setLeads((ls) => ls.map((l) => (l.id === lead.id ? { ...l, status: next } : l)));
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Update failed");
    } finally {
      setBusy(null);
    }
  };

  const newCount = leads.filter((l) => l.status === "new").length;

  return (
    <>
      <PageHeader
        title="Leads"
        subtitle="Callback requests captured by your chatbots."
        actions={
          newCount > 0 ? <Badge kind="warn">{newCount} new</Badge> : undefined
        }
      />
      <Card title={`All leads (${leads.length})`}>
        {loading ? (
          <Spinner />
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : leads.length === 0 ? (
          <EmptyState
            title="No leads yet"
            hint="When a visitor submits the callback form, they appear here."
          />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Phone</th>
                <th>Email</th>
                <th>Chatbot</th>
                <th>When</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {leads.map((l) => (
                <tr key={l.id} className={l.status === "contacted" ? "row-muted" : ""}>
                  <td>{l.name}</td>
                  <td className="mono">
                    <a href={`tel:${l.phone}`}>{l.phone}</a>
                  </td>
                  <td className="mono">
                    {l.email ? <a href={`mailto:${l.email}`}>{l.email}</a> : "—"}
                  </td>
                  <td>{bots[l.chatbot_id] || "—"}</td>
                  <td className="muted">{new Date(l.created_at).toLocaleString()}</td>
                  <td>
                    {l.status === "new" ? (
                      <Badge kind="warn">new</Badge>
                    ) : (
                      <Badge kind="success">contacted</Badge>
                    )}
                  </td>
                  <td className="right">
                    <Button
                      variant="secondary"
                      loading={busy === l.id}
                      onClick={() => toggle(l)}
                    >
                      {l.status === "new" ? "Mark contacted" : "Mark new"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
