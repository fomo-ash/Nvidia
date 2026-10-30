import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

interface AuthContextValue {
  isAuthenticated: boolean;
  csrfToken: string | null;
  busy: boolean;
  error: string | null;
  login: (secret: string) => Promise<boolean>;
  logout: () => void;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const base = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export function AuthProvider({ children }: { children: ReactNode }) {
  const [csrfToken, setCsrfToken] = useState<string | null>(() => sessionStorage.getItem("fixproof_csrf"));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // If we have a CSRF token stored, verify session with target check
    if (csrfToken) {
      try {
        const promise = fetch(`${base}/api/v1/incident-targets`, { credentials: "include" });
        if (promise && typeof promise.then === "function") {
          promise
            .then(res => {
              if (res && (res.status === 401 || res.status === 403)) {
                sessionStorage.removeItem("fixproof_csrf");
                setCsrfToken(null);
              }
            })
            .catch(() => {
              // Network errors should not immediately drop token
            });
        }
      } catch {
        // Safe fallback in test environments
      }
    }
  }, [csrfToken]);

  async function login(secret: string): Promise<boolean> {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${base}/api/v1/session`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ secret }),
      });

      if (!response.ok) {
        let msg = `Authentication failed (${response.status})`;
        try {
          const body = (await response.json()) as { detail?: string };
          if (body.detail) msg = body.detail;
        } catch {
          // ignore parsing error
        }
        throw new Error(msg);
      }

      const data = (await response.json()) as { csrf_token: string };
      sessionStorage.setItem("fixproof_csrf", data.csrf_token);
      setCsrfToken(data.csrf_token);
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
      return false;
    } finally {
      setBusy(false);
    }
  }

  function logout() {
    sessionStorage.removeItem("fixproof_csrf");
    setCsrfToken(null);
    setError(null);
  }

  function clearError() {
    setError(null);
  }

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated: Boolean(csrfToken),
        csrfToken,
        busy,
        error,
        login,
        logout,
        clearError,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
