import { useEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import { ApiError, type DocumentInfo } from "../../api/types";
import { useToast } from "../../components/Toast";
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Spinner,
} from "../../components/ui";
import { useBot } from "./ChatbotLayout";

const ACCEPT = ".pdf,.docx,.txt,.md";

function statusBadge(s: DocumentInfo["status"]) {
  const kind = s === "done" ? "success" : s === "failed" ? "danger" : "warn";
  return <Badge kind={kind}>{s}</Badge>;
}

export default function DocumentsPage() {
  const { bot } = useBot();
  const toast = useToast();
  const [docs, setDocs] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [toDelete, setToDelete] = useState<DocumentInfo | null>(null);
  const [deleting, setDeleting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = (silent = false) => {
    if (!silent) setLoading(true);
    api
      .listDocs(bot.id)
      .then((r) => setDocs(r.documents))
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  };
  useEffect(() => load(), [bot.id]);

  // Poll while any doc is still processing.
  useEffect(() => {
    if (!docs.some((d) => d.status === "processing")) return;
    const t = setInterval(() => load(true), 2000);
    return () => clearInterval(t);
  }, [docs]);

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await api.uploadDoc(bot.id, file);
      toast.success(`Uploading "${file.name}" — processing…`);
      load(true);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const remove = async () => {
    if (!toDelete) return;
    setDeleting(true);
    try {
      await api.deleteDoc(bot.id, toDelete.id);
      toast.success("Document deleted");
      setToDelete(null);
      load(true);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <Card
      title="Documents"
      actions={
        <>
          <input
            ref={fileRef}
            type="file"
            accept={ACCEPT}
            hidden
            onChange={onFile}
          />
          <Button loading={uploading} onClick={() => fileRef.current?.click()}>
            + Upload document
          </Button>
        </>
      }
    >
      {loading ? (
        <Spinner />
      ) : error ? (
        <ErrorState message={error} onRetry={() => load()} />
      ) : docs.length === 0 ? (
        <EmptyState
          title="No documents"
          hint="Upload PDF, DOCX, TXT, or MD files to ground this chatbot's answers."
        />
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Filename</th>
              <th>Status</th>
              <th>Chunks</th>
              <th>Uploaded</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {docs.map((d) => (
              <tr key={d.id}>
                <td className="mono">{d.filename}</td>
                <td>
                  {statusBadge(d.status)}
                  {d.status === "failed" && d.error && (
                    <span className="err-text" title={d.error}>
                      {" "}
                      {d.error.slice(0, 40)}
                    </span>
                  )}
                </td>
                <td>{d.chunk_count}</td>
                <td className="muted">{new Date(d.created_at).toLocaleString()}</td>
                <td className="right">
                  <button className="icon-btn danger" onClick={() => setToDelete(d)}>
                    🗑
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {toDelete && (
        <ConfirmDialog
          title="Delete document"
          message={`Delete "${toDelete.filename}" and purge its vectors?`}
          onConfirm={remove}
          onCancel={() => setToDelete(null)}
          loading={deleting}
        />
      )}
    </Card>
  );
}
