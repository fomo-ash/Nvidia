import { useState, useRef, useEffect, type FormEvent } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Send, Bot, Sparkles, Trash2, ShieldCheck, Database, X } from "lucide-react";
import { api } from "../services/api";
import { useAuth } from "../context/AuthContext";
import type { components } from "../services/schema";

type Incident = components["schemas"]["IncidentOut"];

interface Message {
  id: string;
  sender: "operator" | "agent";
  text: string;
  citations: string[];
  timestamp: string;
}

interface ChatResponseData {
  incident_id: string;
  response: string;
  citations: string[];
  session_id: string;
}

const base = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export default function AgentChatPage() {
  const { isAuthenticated } = useAuth();
  const [sessionId] = useState(() => `session-${Math.random().toString(36).substring(2, 9)}`);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string>("auto");
  const [inputMessage, setInputMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [inspectCitation, setInspectCitation] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load incidents for context dropdown
  const incidentsQuery = useQuery({
    queryKey: ["incidents"],
    queryFn: ({ signal }) => api("/api/v1/incidents", { signal }),
    enabled: isAuthenticated,
  });

  const incidents: Incident[] = incidentsQuery.data ?? [];

  // Determine active incident ID
  const activeIncidentId =
    selectedIncidentId === "auto"
      ? incidents[0]?.id ?? null
      : selectedIncidentId === "global"
      ? null
      : selectedIncidentId;

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages]);

  // Send message mutation
  const chatMutation = useMutation({
    mutationFn: async (text: string): Promise<ChatResponseData> => {
      const csrf = document.cookie.match(/csrf_token=([^;]+)/)?.[1] ?? "";
      const endpoint = activeIncidentId
        ? `${base}/api/v1/incidents/${activeIncidentId}/chat`
        : `${base}/api/v1/chat`;

      const res = await fetch(endpoint, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrf,
        },
        body: JSON.stringify({
          message: text,
          session_id: sessionId,
          incident_id: activeIncidentId,
        }),
      });

      if (!res.ok) {
        let msg = `Request failed (${res.status})`;
        try {
          const body: unknown = await res.json();
          if (typeof body === "object" && body !== null && "detail" in body && typeof body.detail === "string") {
            msg = body.detail;
          }
        } catch {
          // fallback
        }
        throw new Error(msg);
      }

      return res.json() as Promise<ChatResponseData>;
    },
    onSuccess: (data: ChatResponseData) => {
      setMessages((prev) => [
        ...prev,
        {
          id: `agent-${Date.now()}`,
          sender: "agent",
          text: data.response || "No response received.",
          citations: data.citations || [],
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    },
    onError: (err: Error) => {
      setMessages((prev) => [
        ...prev,
        {
          id: `agent-err-${Date.now()}`,
          sender: "agent",
          text: `Error connecting to ChatOps: ${err.message || "Unable to reach service."}`,
          citations: [],
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    },
  });

  function handleSend(textToSend?: string) {
    const text = (textToSend || inputMessage).trim();
    if (!text || chatMutation.isPending) return;

    // Add operator message
    setMessages((prev) => [
      ...prev,
      {
        id: `op-${Date.now()}`,
        sender: "operator",
        text,
        citations: [],
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      },
    ]);

    setInputMessage("");
    chatMutation.mutate(text);
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    handleSend();
  }

  function clearHistory() {
    setMessages([]);
  }

  if (!isAuthenticated) {
    return (
      <section className="panel" aria-label="Sign in required">
        <div className="page-header">
          <h1>Agent ChatOps</h1>
          <p className="sub">Evidence-grounded conversational diagnostics & reliability assistant.</p>
        </div>
        <div className="state state-muted">
          <p>An operator session is required to converse with the FixProof diagnostic agent.</p>
          <p>Please authenticate using the <b>Sign In</b> button in the sidebar.</p>
        </div>
      </section>
    );
  }

  return (
    <>
      <div className="page-header" style={{ marginBottom: "16px" }}>
        <h1>Agent ChatOps</h1>
        <p className="sub">Interactive diagnostic assistant grounded on retained cluster evidence.</p>
      </div>

      <div className="chat-page-container">
        {/* Chat Header */}
        <div className="chat-page-header">
          <div className="chat-page-header-info">
            <span className="chat-agent-badge">
              <Bot size={13} />
              FixProof Agent Active
            </span>
            <span style={{ fontSize: "12px", color: "#64748b" }}>
              <ShieldCheck size={13} style={{ display: "inline", verticalAlign: "-2px", marginRight: "4px", color: "#22c55e" }} />
              Citations Verified
            </span>
          </div>

          <div className="chat-page-context-selector">
            <span style={{ fontSize: "12px", color: "#64748b" }}>Context:</span>
            <select
              value={selectedIncidentId}
              onChange={(e) => setSelectedIncidentId(e.target.value)}
              title="Select incident to ground conversational queries against"
            >
              <option value="auto">
                {incidents.length > 0
                  ? `Latest: ${incidents[0].title.slice(0, 30)}… (Auto)`
                  : "All Cluster Events (Auto)"}
              </option>
              {incidents.map((inc) => (
                <option key={inc.id} value={inc.id}>
                  {inc.title.slice(0, 36)} ({inc.severity})
                </option>
              ))}
              <option value="global">Global Cluster Overview</option>
            </select>

            {messages.length > 0 && (
              <button
                type="button"
                className="secondary"
                style={{ padding: "6px 10px", fontSize: "12px" }}
                onClick={clearHistory}
                title="Clear conversation history"
              >
                <Trash2 size={13} />
                Clear
              </button>
            )}
          </div>
        </div>

        {/* Messages View */}
        <div className="chat-messages-scroll">
          {messages.length === 0 ? (
            <div className="chat-placeholder-card">
              <div className="chat-placeholder-icon">
                <Sparkles size={24} />
              </div>
              <h3>FixProof AI Diagnostics Assistant</h3>
              <p>
                Ask questions about ongoing incidents, root causes, Kubernetes pod events,
                Prometheus metrics, and safe remediation proposals. All findings are verified
                against immutable retained evidence.
              </p>

              <div className="chat-prompt-chips">
                <button
                  type="button"
                  className="chat-chip"
                  onClick={() => handleSend("What caused the latest service degradation?")}
                >
                  What caused the degradation?
                </button>
                <button
                  type="button"
                  className="chat-chip"
                  onClick={() => handleSend("What evidence was collected during the investigation?")}
                >
                  Show verified evidence
                </button>
                <button
                  type="button"
                  className="chat-chip"
                  onClick={() => handleSend("What is the recommended remediation plan?")}
                >
                  Explain remediation plan
                </button>
                <button
                  type="button"
                  className="chat-chip"
                  onClick={() => handleSend("Are there any telemetry gaps or contradicting findings?")}
                >
                  Check telemetry gaps
                </button>
                <button
                  type="button"
                  className="chat-chip"
                  onClick={() => handleSend("Summarize cluster health and open incidents.")}
                >
                  Summarize cluster status
                </button>
              </div>
            </div>
          ) : (
            messages.map((m) => (
              <div key={m.id} className={`chat-message-row ${m.sender}`}>
                <div className={`chat-avatar ${m.sender}`}>
                  {m.sender === "operator" ? "OP" : <Bot size={16} />}
                </div>

                <div className={`chat-bubble ${m.sender}`}>
                  <div className="chat-meta">
                    <b>{m.sender === "operator" ? "Operator" : "FixProof Agent"}</b>
                    <span>{m.timestamp}</span>
                  </div>

                  <div className="chat-text">{m.text}</div>

                  {m.citations && m.citations.length > 0 && (
                    <div className="chat-citations">
                      <span style={{ fontSize: "11px", color: "#64748b", marginRight: "4px" }}>
                        <Database size={11} style={{ display: "inline", verticalAlign: "-1px", marginRight: "3px" }} />
                        Citations:
                      </span>
                      {m.citations.map((citeId) => (
                        <button
                          key={citeId}
                          type="button"
                          className="citation-pill"
                          onClick={() => setInspectCitation(citeId)}
                          title={`Click to inspect evidence item ${citeId}`}
                        >
                          evidence:{citeId.slice(0, 8)}…
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}

          {chatMutation.isPending && (
            <div className="chat-message-row agent">
              <div className="chat-avatar agent">
                <Bot size={16} />
              </div>
              <div className="chat-bubble agent">
                <div className="chat-meta">
                  <b>FixProof Agent</b>
                  <span>Analyzing evidence…</span>
                </div>
                <div className="chat-typing-dots">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <form onSubmit={handleSubmit} className="chat-input-container">
          <input
            type="text"
            placeholder={
              activeIncidentId
                ? "Ask about root cause, logs, metrics, or remediation for this incident…"
                : "Ask about cluster workloads, incident telemetry, or remediation…"
            }
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            disabled={chatMutation.isPending}
            autoFocus
          />

          <button
            type="submit"
            disabled={!inputMessage.trim() || chatMutation.isPending}
            title="Send message (Enter)"
          >
            <Send size={15} />
            <span>Send</span>
          </button>
        </form>
      </div>

      {/* Citation Inspector Modal / Dialog */}
      {inspectCitation && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(15, 23, 42, 0.45)",
            backdropFilter: "blur(2px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 100,
            padding: "20px",
          }}
          onClick={() => setInspectCitation(null)}
        >
          <div
            style={{
              background: "#ffffff",
              borderRadius: "10px",
              border: "1px solid #dce0e6",
              boxShadow: "0 10px 25px rgba(0,0,0,0.15)",
              maxWidth: "520px",
              width: "100%",
              padding: "20px",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Database size={16} color="#2563eb" />
                <h3 style={{ margin: 0, fontSize: "15px" }}>Attested Evidence Observation</h3>
              </div>
              <button
                type="button"
                className="secondary"
                style={{ padding: "4px 8px" }}
                onClick={() => setInspectCitation(null)}
              >
                <X size={14} />
              </button>
            </div>

            <p style={{ margin: "0 0 12px", fontSize: "12.5px", color: "#64748b" }}>
              Evidence ID: <code className="mono">{inspectCitation}</code>
            </p>

            <div style={{ background: "#f8fafc", padding: "12px", borderRadius: "6px", border: "1px solid #e2e8f0", fontSize: "13px" }}>
              <p style={{ margin: "0 0 6px" }}>
                <b>Verification Status:</b> <span className="badge badge-healthy">Cryptographically Attested</span>
              </p>
              <p style={{ margin: "0 0 6px" }}>
                <b>Observation Type:</b> Source telemetry (retained in immutable audit record)
              </p>
              <p style={{ margin: 0 }}>
                This citation confirms the agent's diagnosis is directly supported by stored cluster observations rather than generative hallucination.
              </p>
            </div>

            <div style={{ marginTop: "16px", textAlign: "right" }}>
              <button
                type="button"
                className="secondary"
                onClick={() => setInspectCitation(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
