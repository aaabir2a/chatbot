import { useEffect, useState } from "react";
import { api, apiBaseUrl } from "../api/client";
import { ApiError, type CrmKeyCreated, type CrmKeyInfo } from "../api/types";
import { PageHeader } from "../components/Layout";
import { useToast } from "../components/Toast";
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Field,
  Input,
  Modal,
  Spinner,
} from "../components/ui";

export default function Integrations() {
  const toast = useToast();
  const base = apiBaseUrl();
  const [keys, setKeys] = useState<CrmKeyInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("my-crm");
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<CrmKeyCreated | null>(null);
  const [toRevoke, setToRevoke] = useState<CrmKeyInfo | null>(null);
  const [revoking, setRevoking] = useState(false);

  const load = () => {
    setLoading(true);
    api
      .listCrmKeys()
      .then(setKeys)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const create = async () => {
    setCreating(true);
    try {
      const k = await api.createCrmKey(name || "default");
      setShowCreate(false);
      setName("my-crm");
      setCreated(k);
      load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Create failed");
    } finally {
      setCreating(false);
    }
  };

  const revoke = async () => {
    if (!toRevoke) return;
    setRevoking(true);
    try {
      await api.revokeCrmKey(toRevoke.id);
      toast.success("CRM key revoked");
      setToRevoke(null);
      load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Revoke failed");
    } finally {
      setRevoking(false);
    }
  };

  const copy = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard");
  };

  const endpoints = [
    ["GET", "/crm/chatbots", "List your chatbots"],
    ["GET", "/crm/conversations?limit=50&since=ISO", "List conversations (paginated)"],
    ["GET", "/crm/conversations/{id}/messages", "Full transcript of a conversation"],
    ["GET", "/crm/leads?status=new&since=ISO", "Leads from the callback form"],
  ];

  return (
    <>
      <PageHeader
        title="Integrations (CRM API)"
        subtitle="Pull conversations, transcripts, and leads into your CRM with an API key — no login."
        actions={<Button onClick={() => setShowCreate(true)}>+ Generate CRM key</Button>}
      />

      <Card title="CRM API keys">
        {loading ? (
          <Spinner />
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : keys.length === 0 ? (
          <EmptyState
            title="No CRM keys yet"
            hint="Generate a key, then your CRM can read conversations and leads."
          />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Key</th>
                <th>Status</th>
                <th>Last used</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <tr key={k.id} className={k.revoked ? "row-muted" : ""}>
                  <td>{k.name}</td>
                  <td className="mono">{k.prefix}••••••••</td>
                  <td>
                    {k.revoked ? (
                      <Badge kind="danger">revoked</Badge>
                    ) : (
                      <Badge kind="success">active</Badge>
                    )}
                  </td>
                  <td className="muted">
                    {k.last_used_at ? new Date(k.last_used_at).toLocaleString() : "—"}
                  </td>
                  <td className="right">
                    {!k.revoked && (
                      <button className="icon-btn danger" onClick={() => setToRevoke(k)}>
                        Revoke
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card title="How to use it">
        <p className="muted" style={{ marginTop: 0 }}>
          Send your CRM key in the <code>X-CRM-Key</code> header. Base URL:
          <code> {base}</code>
        </p>
        <table className="table">
          <thead>
            <tr>
              <th>Method</th>
              <th>Endpoint</th>
              <th>Returns</th>
            </tr>
          </thead>
          <tbody>
            {endpoints.map(([m, p, d]) => (
              <tr key={p}>
                <td>
                  <Badge kind="success">{m}</Badge>
                </td>
                <td className="mono">{p}</td>
                <td className="muted">{d}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="field-label" style={{ marginTop: 16 }}>
          Example
        </p>
        <div className="key-reveal" style={{ alignItems: "flex-start" }}>
          <code style={{ whiteSpace: "pre-wrap" }}>
            {`curl -H "X-CRM-Key: crm_your_key" \\\n  "${base}/crm/leads?status=new"`}
          </code>
          <Button
            variant="secondary"
            onClick={() =>
              copy(`curl -H "X-CRM-Key: crm_your_key" "${base}/crm/leads?status=new"`)
            }
          >
            Copy
          </Button>
        </div>
      </Card>

      {showCreate && (
        <Modal
          title="Generate CRM key"
          onClose={() => setShowCreate(false)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setShowCreate(false)}>
                Cancel
              </Button>
              <Button onClick={create} loading={creating}>
                Generate
              </Button>
            </>
          }
        >
          <Field label="Key name" hint="A label so you know which CRM/integration uses it.">
            <Input value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          </Field>
        </Modal>
      )}

      {created && (
        <Modal
          title="Copy your CRM key"
          onClose={() => setCreated(null)}
          footer={<Button onClick={() => setCreated(null)}>Done</Button>}
        >
          <p className="warn-note">
            This is the only time the full key is shown. Store it in your CRM securely.
          </p>
          <div className="key-reveal">
            <code>{created.api_key}</code>
            <Button variant="secondary" onClick={() => copy(created.api_key)}>
              Copy
            </Button>
          </div>
        </Modal>
      )}

      {toRevoke && (
        <ConfirmDialog
          title="Revoke CRM key"
          message={`Revoke "${toRevoke.name}" (${toRevoke.prefix}…)? Any CRM using it will immediately lose access.`}
          confirmLabel="Revoke"
          onConfirm={revoke}
          onCancel={() => setToRevoke(null)}
          loading={revoking}
        />
      )}
    </>
  );
}
