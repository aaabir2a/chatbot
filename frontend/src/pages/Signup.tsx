import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { Button, Field, Input } from "../components/ui";
import { ApiError } from "../api/types";

export default function Signup() {
  const { signup } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 8) {
      toast.error("Password must be at least 8 characters");
      return;
    }
    setLoading(true);
    try {
      await signup(name, email, password);
      navigate("/");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Signup failed");
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
        <h2>Create your organization</h2>
        <p className="auth-sub">Start building chatbots in minutes</p>
        <Field label="Organization name">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Acme Inc."
            required
          />
        </Field>
        <Field label="Email">
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            required
          />
        </Field>
        <Field label="Password" hint="At least 8 characters">
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            required
          />
        </Field>
        <Button type="submit" loading={loading} className="full">
          Create account
        </Button>
        <p className="auth-foot">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </form>
    </div>
  );
}
