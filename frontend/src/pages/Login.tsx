import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { Button, Field, Input } from "../components/ui";
import { ApiError } from "../api/types";

export default function Login() {
  const { login } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <div className="auth-brand">
          <span className="brand-mark">◆</span> RAG Console
        </div>
        <h2>Welcome back</h2>
        <p className="auth-sub">Sign in to your organization</p>
        <Field label="Email">
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            required
          />
        </Field>
        <Field label="Password">
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            required
          />
        </Field>
        <Button type="submit" loading={loading} className="full">
          Sign in
        </Button>
        <p className="auth-foot">
          No account? <Link to="/signup">Create one</Link>
        </p>
      </form>
    </div>
  );
}
