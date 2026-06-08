import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { ApiError, type Chatbot, type ChatbotInput } from "../api/types";
import { PageHeader } from "../components/Layout";
import { useToast } from "../components/Toast";
import {
  Button,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Field,
  Input,
  Modal,
  Spinner,
  Textarea,
} from "../components/ui";

const DEFAULT_FORM: ChatbotInput = {
  name: "",
  system_prompt: "You are a helpful assistant.",
  tone: "friendly and professional",
  welcome_message: "Hi! How can I help you today?",
  model: "qwen2.5:3b",
};

export default function Chatbots() {
  const navigate = useNavigate();
  const toast = useToast();
  const [bots, setBots] = useState<Chatbot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<ChatbotInput>(DEFAULT_FORM);
  const [saving, setSaving] = useState(false);
  const [toDelete, setToDelete] = useState<Chatbot | null>(null);
  const [deleting, setDeleting] = useState(false);

  const load = () => {
    setLoading(true);
    setError(null);
    api
      .listChatbots()
      .then(setBots)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const create = async () => {
    if (!form.name?.trim()) {
      toast.error("Name is required");
      return;
    }
    setSaving(true);
    try {
      const bot = await api.createChatbot(form);
      toast.success("Chatbot created");
      setShowCreate(false);
      setForm(DEFAULT_FORM);
      navigate(`/chatbots/${bot.id}/config`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Create failed");
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!toDelete) return;
    setDeleting(true);
    try {
      await api.deleteChatbot(toDelete.id);
      toast.success("Chatbot deleted");
      setToDelete(null);
      load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Chatbots"
        subtitle="Each chatbot has isolated documents, keys, and config."
        actions={<Button onClick={() => setShowCreate(true)}>+ New chatbot</Button>}
      />

      {loading ? (
        <Spinner />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : bots.length === 0 ? (
        <EmptyState
          title="No chatbots yet"
          hint="Create your first chatbot to start ingesting documents."
          action={<Button onClick={() => setShowCreate(true)}>+ New chatbot</Button>}
        />
      ) : (
        <div className="grid">
          {bots.map((b) => (
            <div
              key={b.id}
              className="bot-card"
              onClick={() => navigate(`/chatbots/${b.id}/config`)}
            >
              <div className="bot-card-top">
                <div className="bot-avatar">{b.name[0]?.toUpperCase()}</div>
                <button
                  className="icon-btn danger"
                  title="Delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    setToDelete(b);
                  }}
                >
                  🗑
                </button>
              </div>
              <h3 className="bot-name">{b.name}</h3>
              <p className="bot-prompt">{b.system_prompt}</p>
              <div className="bot-meta">
                <span className="tag">{b.model}</span>
                <span className="tag tag-soft">{b.tone}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <Modal
          title="New chatbot"
          onClose={() => setShowCreate(false)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setShowCreate(false)}>
                Cancel
              </Button>
              <Button onClick={create} loading={saving}>
                Create
              </Button>
            </>
          }
        >
          <Field label="Name">
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Support bot"
              autoFocus
            />
          </Field>
          <Field label="System prompt">
            <Textarea
              rows={3}
              value={form.system_prompt}
              onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
            />
          </Field>
          <div className="row">
            <Field label="Tone">
              <Input
                value={form.tone}
                onChange={(e) => setForm({ ...form, tone: e.target.value })}
              />
            </Field>
            <Field label="Model">
              <Input
                value={form.model}
                onChange={(e) => setForm({ ...form, model: e.target.value })}
              />
            </Field>
          </div>
        </Modal>
      )}

      {toDelete && (
        <ConfirmDialog
          title="Delete chatbot"
          message={`Delete "${toDelete.name}"? This purges its documents, vectors, keys, and logs. This cannot be undone.`}
          onConfirm={remove}
          onCancel={() => setToDelete(null)}
          loading={deleting}
        />
      )}
    </>
  );
}
