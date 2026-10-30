import { useState, type FormEvent } from "react";
import { useAuth } from "../context/AuthContext";
import { useQueryClient } from "@tanstack/react-query";

export default function OperatorSessionBar() {
  const { isAuthenticated, busy, error, login, logout, clearError } = useAuth();
  const [secret, setSecret] = useState("");
  const [showInput, setShowInput] = useState(false);
  const queryClient = useQueryClient();

  async function handleLogin(e: FormEvent) {
    e.preventDefault();
    if (!secret.trim()) return;
    const ok = await login(secret.trim());
    if (ok) {
      setSecret("");
      setShowInput(false);
      // Invalidate queries so overview and incidents auto-reload
      await queryClient.invalidateQueries();
    }
  }

  function handleLogout() {
    logout();
    queryClient.clear();
  }

  if (isAuthenticated) {
    return (
      <div className="session-status session-authenticated" role="region" aria-label="Session status">
        <span className="session-indicator active">●</span>
        <span className="session-label">Operator Active</span>
        <button
          type="button"
          className="session-action-btn"
          onClick={handleLogout}
          title="Sign out of operator session"
        >
          Sign out
        </button>
      </div>
    );
  }

  return (
    <div className="session-status session-unauthenticated" role="region" aria-label="Session status">
      {!showInput ? (
        <div className="session-prompt">
          <span className="session-indicator inactive">○</span>
          <span className="session-label">Unauthenticated</span>
          <button
            type="button"
            className="session-action-btn primary"
            onClick={() => {
              clearError();
              setShowInput(true);
            }}
          >
            Sign In
          </button>
        </div>
      ) : (
        <form onSubmit={handleLogin} className="session-inline-form">
          <input
            type="password"
            placeholder="Operator secret..."
            value={secret}
            onChange={e => setSecret(e.target.value)}
            disabled={busy}
            autoFocus
          />
          <div className="session-form-actions">
            <button type="submit" disabled={busy || !secret.trim()} className="session-action-btn primary">
              {busy ? "Signing in…" : "Sign in"}
            </button>
            <button
              type="button"
              className="session-action-btn"
              disabled={busy}
              onClick={() => {
                clearError();
                setShowInput(false);
              }}
            >
              Cancel
            </button>
          </div>
          {error && <small className="session-error" role="alert">{error}</small>}
        </form>
      )}
    </div>
  );
}

