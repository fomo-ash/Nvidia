import { useState, useRef, useEffect, type FormEvent } from "react";
import { Send, Sparkles, X, ChevronRight, AlertCircle, Bot, User } from "lucide-react";

interface ChatMessage {
  id: string;
  sender: "operator" | "agent";
  text: string;
  citations: string[];
  timestamp: string;
}

const base = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export default function IncidentChatDrawer({ incidentId }: { incidentId: string }) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    {
      id: "welcome",
      sender: "agent",
      text: "Hello, I am your FixProof ChatOps Assistant. I am grounded in this incident's retained evidence. You can ask me questions about metric anomalies, pod logs, probe failures, or causal hypotheses.",
      citations: [],
      timestamp: new Date().toLocaleTimeString(),
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [sessionId] = useState<string>(() => {
    let sid = sessionStorage.getItem(`chat_session_${incidentId}`);
    if (!sid) {
      sid = crypto.randomUUID();
      sessionStorage.setItem(`chat_session_${incidentId}`, sid);
    }
    return sid;
  });

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isOpen]);

  async function handleSend(e?: FormEvent) {
    if (e) e.preventDefault();
    const queryText = input.trim();
    if (!queryText || busy) return;

    const csrf = sessionStorage.getItem("fixproof_csrf");
    if (!csrf) {
      setError("Active operator session required. Please sign in.");
      return;
    }

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      sender: "operator",
      text: queryText,
      citations: [],
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setBusy(true);
    setError(null);

    try {
      const response = await fetch(`${base}/api/v1/incidents/${incidentId}/chat`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrf,
        },
        body: JSON.stringify({
          message: queryText,
          session_id: sessionId,
        }),
      });

      if (!response.ok) {
        let msg = `Chat failed (${response.status})`;
        try {
          const body = (await response.json()) as { detail?: string };
          if (body.detail) msg = body.detail;
        } catch {
          // fallback msg
        }
        throw new Error(msg);
      }

      const data = (await response.json()) as { response: string; citations?: string[] };
      const agentMsg: ChatMessage = {
        id: crypto.randomUUID(),
        sender: "agent",
        text: data.response || "No answer generated.",
        citations: data.citations || [],
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages(prev => [...prev, agentMsg]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to communicate with agent");
    } finally {
      setBusy(false);
    }
  }

  function handlePromptClick(promptText: string) {
    setInput(promptText);
  }

  return (
    <>
      {/* Floating Toggle Button */}
      {!isOpen && (
        <button
          type="button"
          className="chatops-floating-btn"
          onClick={() => setIsOpen(true)}
          aria-label="Open ChatOps Assistant"
        >
          <Sparkles size={16} />
          <span>Ask ChatOps</span>
        </button>
      )}

      {/* Slide-out Drawer */}
      <aside className={`chatops-drawer ${isOpen ? "open" : ""}`} aria-label="Incident ChatOps Assistant">
        <div className="chatops-header">
          <div className="chatops-title">
            <Bot size={18} className="chatops-icon" />
            <div>
              <h4>FixProof ChatOps</h4>
              <small>Grounded in incident evidence</small>
            </div>
          </div>
          <button
            type="button"
            className="secondary chatops-close-btn"
            onClick={() => setIsOpen(false)}
            aria-label="Close chat drawer"
          >
            <X size={16} />
          </button>
        </div>

        {/* Quick Suggestion Chips */}
        <div className="chatops-suggestions">
          <button
            type="button"
            className="suggestion-chip"
            onClick={() => handlePromptClick("What is the root cause according to collected evidence?")}
          >
            Root cause summary
          </button>
          <button
            type="button"
            className="suggestion-chip"
            onClick={() => handlePromptClick("Explain why /healthz failed while /readyz stayed 200")}
          >
            Probe discrepancies
          </button>
          <button
            type="button"
            className="suggestion-chip"
            onClick={() => handlePromptClick("What are the Prometheus error rate readings?")}
          >
            Traffic metrics
          </button>
        </div>

        {/* Messages Stream */}
        <div className="chatops-messages">
          {messages.map(msg => (
            <div key={msg.id} className={`chatops-bubble ${msg.sender}`}>
              <div className="bubble-meta">
                {msg.sender === "agent" ? <Bot size={12} /> : <User size={12} />}
                <span>{msg.sender === "agent" ? "ChatOps Agent" : "Operator"}</span>
                <time>{msg.timestamp}</time>
              </div>
              <div className="bubble-text">{msg.text}</div>

              {msg.citations && msg.citations.length > 0 && (
                <div className="bubble-citations">
                  <span className="citations-label">Verified Citations:</span>
                  {msg.citations.map(cid => (
                    <a
                      key={cid}
                      href={`#evidence-${cid}`}
                      className="citation-pill"
                      title={`Jump to evidence ${cid}`}
                      onClick={() => {
                        const target = document.getElementById(`evidence-${cid}`);
                        if (target) {
                          target.scrollIntoView({ behavior: "smooth", block: "center" });
                          target.classList.add("highlighted-evidence");
                          setTimeout(() => target.classList.remove("highlighted-evidence"), 2500);
                        }
                      }}
                    >
                      <ChevronRight size={10} />
                      <span>{cid.slice(0, 8)}…</span>
                    </a>
                  ))}
                </div>
              )}
            </div>
          ))}
          {busy && (
            <div className="chatops-bubble agent typing">
              <span className="dot"></span>
              <span className="dot"></span>
              <span className="dot"></span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Error Notification */}
        {error && (
          <div className="chatops-error" role="alert">
            <AlertCircle size={14} />
            <span>{error}</span>
          </div>
        )}

        {/* Chat Input */}
        <form onSubmit={handleSend} className="chatops-input-bar">
          <input
            type="text"
            placeholder="Ask about logs, metrics, or evidence…"
            value={input}
            onChange={e => setInput(e.target.value)}
            disabled={busy}
          />
          <button type="submit" disabled={busy || !input.trim()} aria-label="Send message">
            <Send size={15} />
          </button>
        </form>
      </aside>
    </>
  );
}
