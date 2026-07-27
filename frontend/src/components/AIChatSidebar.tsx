"use client";

import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import { ChatMessage } from "@/lib/chat";

type AIChatSidebarProps = {
  open: boolean;
  messages: ChatMessage[];
  loading: boolean;
  error: string | null;
  onClose: () => void;
  onSend: (message: string) => void;
};

export function AIChatSidebar({ open, messages, loading, error, onClose, onSend }: AIChatSidebarProps) {
  const [draft, setDraft] = useState("");
  const messagesRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = messagesRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages.length, loading, open]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const trimmed = draft.trim();
    if (!trimmed || loading) return;
    onSend(trimmed);
    setDraft("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      const trimmed = draft.trim();
      if (trimmed && !loading) {
        onSend(trimmed);
        setDraft("");
      }
    }
  }

  return (
    <aside className={`ai-sidebar ${open ? "is-open" : ""}`} aria-label="AI assistant" aria-hidden={!open}>
      <header className="ai-sidebar-head">
        <div>
          <p className="eyebrow">ASSISTANT</p>
          <h2>Ask Momentum AI</h2>
        </div>
        <button type="button" className="ai-close" aria-label="Close AI assistant" onClick={onClose}>×</button>
      </header>

      <div className="ai-messages" ref={messagesRef} role="log" aria-live="polite">
        {messages.length === 0 ? (
          <p className="ai-empty">Ask me to create, move, or delete cards, or to rename a column.</p>
        ) : (
          messages.map((message) => (
            <div key={message.id} className={`ai-message ai-message-${message.role}`}>
              <span className="ai-message-role">{message.role === "user" ? "You" : "AI"}</span>
              <p className="ai-message-text">{message.content}</p>
            </div>
          ))
        )}
        {loading && <div className="ai-message ai-message-assistant"><span className="ai-message-role">AI</span><p className="ai-message-text ai-typing">Thinking…</p></div>}
        {error && <p className="ai-error" role="alert">{error}</p>}
      </div>

      <form className="ai-input-row" onSubmit={submit}>
        <textarea
          aria-label="Message Momentum AI"
          placeholder="Ask me to update the board…"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          rows={2}
        />
        <button type="submit" className="ai-send" disabled={loading || !draft.trim()}>Send</button>
      </form>
    </aside>
  );
}