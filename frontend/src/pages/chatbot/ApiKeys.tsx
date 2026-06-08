import { useEffect, useState } from "react";
import { api, apiBaseUrl } from "../../api/client";
import { ApiError, type ApiKeyCreated, type ApiKeyInfo } from "../../api/types";
import { useToast } from "../../components/Toast";
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
} from "../../components/ui";
import { useBot } from "./ChatbotLayout";

function embedSnippet(apiKey: string, chatbotId: string): string {
  return `<script
  src="${apiBaseUrl()}/widget.js"
  data-api-url="${apiBaseUrl()}"
  data-api-key="${apiKey}"
  data-chatbot-id="${chatbotId}"
  data-title="Support"
  data-position="bottom-right"></script>`;
}

export default function ApiKeysPage() {
  const { bot } = useBot();
  const toast = useToast();
  const [keys, setKeys] = useState<ApiKeyInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("default");
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<ApiKeyCreated | null>(null);
  const [toRevoke, setToRevoke] = useState<ApiKeyInfo | null>(null);
  const [revoking, setRevoking] = useState(false);

  const load = () => {
    setLoading(true);
    api
      .listKeys(bot.id)
      .then(setKeys)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  };
  useEffect(load, [bot.id]);

  const create = async () => {
    setCreating(true);
    try {
      const k = await api.createKey(bot.id, name || "default");
      setShowCreate(false);
      setName("default");
      setCreated(k); // show-once modal
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
      await api.revokeKey(toRevoke.id);
      toast.success("Key revoked");
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

  return (
    <>
    <Card title="Chatbot ID">
      <p className="muted small" style={{ marginTop: 0 }}>
        Use this as <code>data-chatbot-id</code> in the embed snippet.
      </p>
      <div className="key-reveal">
        <code>{bot.id}</code>
        <Button variant="secondary" onClick={() => copy(bot.id)}>
          Copy
        </Button>
      </div>
    </Card>

    <Card
      title="API Keys"
      actions={<Button onClick={() => setShowCreate(true)}>+ Generate key</Button>}
    >
      {loading ? (
        <Spinner />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : keys.length === 0 ? (
        <EmptyState
          title="No API keys"
          hint="Generate a key to call /ingest and /chat for this chatbot."
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

      {showCreate && (
        <Modal
          title="Generate API key"
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
          <Field label="Key name" hint="A label to recognize this key later.">
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="production-web"
              autoFocus
            />
          </Field>
        </Modal>
      )}

      {created && (
        <Modal
          title="Copy your API key"
          onClose={() => setCreated(null)}
          footer={
            <Button onClick={() => setCreated(null)}>Done</Button>
          }
        >
          <p className="warn-note">
            This is the only time the full key is shown. Store it securely.
          </p>
          <div className="key-reveal">
            <code>{created.api_key}</code>
            <Button variant="secondary" onClick={() => copy(created.api_key)}>
              Copy
            </Button>
          </div>

          <p className="field-label" style={{ marginTop: 18 }}>
            Drop-in embed snippet
          </p>
          <p className="muted small" style={{ marginTop: 4 }}>
            Paste into any site. Includes this key and the chatbot id.
          </p>
          <div className="key-reveal" style={{ alignItems: "flex-start" }}>
            <code style={{ whiteSpace: "pre-wrap" }}>{embedSnippet(created.api_key, bot.id)}</code>
            <Button
              variant="secondary"
              onClick={() => copy(embedSnippet(created.api_key, bot.id))}
            >
              Copy
            </Button>
          </div>
        </Modal>
      )}

      {toRevoke && (
        <ConfirmDialog
          title="Revoke API key"
          message={`Revoke "${toRevoke.name}" (${toRevoke.prefix}…)? Clients using it will immediately get 401.`}
          confirmLabel="Revoke"
          onConfirm={revoke}
          onCancel={() => setToRevoke(null)}
          loading={revoking}
        />
      )}
    </Card>
    </>
  );
}
