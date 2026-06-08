import {
  type ButtonHTMLAttributes,
  type ReactNode,
  type InputHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";

// ── Button ──
type Variant = "primary" | "secondary" | "danger" | "ghost";
export function Button({
  variant = "primary",
  loading,
  children,
  className = "",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  loading?: boolean;
}) {
  return (
    <button
      className={`btn btn-${variant} ${className}`}
      disabled={loading || rest.disabled}
      {...rest}
    >
      {loading ? <span className="spinner spinner-sm" /> : children}
    </button>
  );
}

// ── Card ──
export function Card({
  title,
  actions,
  children,
}: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="card">
      {(title || actions) && (
        <div className="card-head">
          <h3>{title}</h3>
          <div>{actions}</div>
        </div>
      )}
      <div className="card-body">{children}</div>
    </div>
  );
}

// ── Badge ──
export function Badge({ kind, children }: { kind: string; children: ReactNode }) {
  return <span className={`badge badge-${kind}`}>{children}</span>;
}

// ── Spinner / states ──
export function Spinner() {
  return (
    <div className="center pad">
      <span className="spinner" />
    </div>
  );
}

export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">∅</div>
      <p className="empty-title">{title}</p>
      {hint && <p className="empty-hint">{hint}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="empty error-state">
      <div className="empty-icon">!</div>
      <p className="empty-title">Something went wrong</p>
      <p className="empty-hint">{message}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

// ── Form fields ──
export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className="input" {...props} />;
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className="input textarea" {...props} />;
}

// ── Modal ──
export function Modal({
  title,
  onClose,
  children,
  footer,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3>{title}</h3>
          <button className="icon-btn" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}

// ── Confirm dialog ──
export function ConfirmDialog({
  title,
  message,
  confirmLabel = "Delete",
  onConfirm,
  onCancel,
  loading,
}: {
  title: string;
  message: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}) {
  return (
    <Modal
      title={title}
      onClose={onCancel}
      footer={
        <>
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant="danger" onClick={onConfirm} loading={loading}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <p>{message}</p>
    </Modal>
  );
}
