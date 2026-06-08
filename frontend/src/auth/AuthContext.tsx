import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api, tokenStore } from "../api/client";
import type { Org } from "../api/types";

interface AuthState {
  org: Org | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [org, setOrg] = useState<Org | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Restore session from a stored token.
    if (!tokenStore.get()) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then(setOrg)
      .catch(() => tokenStore.clear())
      .finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const res = await api.login(email, password);
    tokenStore.set(res.access_token);
    setOrg(res.org);
  };

  const signup = async (name: string, email: string, password: string) => {
    const res = await api.signup(name, email, password);
    tokenStore.set(res.access_token);
    setOrg(res.org);
  };

  const logout = () => {
    tokenStore.clear();
    setOrg(null);
  };

  return (
    <AuthContext.Provider value={{ org, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
