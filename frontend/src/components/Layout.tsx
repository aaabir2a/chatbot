import { type ReactNode } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function AppLayout() {
  const { org, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">◆</span>
          <span className="brand-name">RAG&nbsp;Console</span>
        </div>
        <nav className="side-nav">
          <NavLink to="/" end className="side-link">
            <span className="side-ico">▣</span> Chatbots
          </NavLink>
          <NavLink to="/live" className="side-link">
            <span className="side-ico">◉</span> Live Chats
          </NavLink>
        </nav>
        <div className="side-foot">
          <div className="org-chip">
            <div className="org-avatar">{org?.name?.[0]?.toUpperCase() ?? "?"}</div>
            <div className="org-meta">
              <div className="org-name">{org?.name}</div>
              <div className="org-email">{org?.email}</div>
            </div>
          </div>
          <button
            className="side-link logout"
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            <span className="side-ico">⏻</span> Log out
          </button>
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  actions,
  back,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  back?: ReactNode;
}) {
  return (
    <header className="page-head">
      <div>
        {back}
        <h1>{title}</h1>
        {subtitle && <p className="page-sub">{subtitle}</p>}
      </div>
      <div className="page-actions">{actions}</div>
    </header>
  );
}
