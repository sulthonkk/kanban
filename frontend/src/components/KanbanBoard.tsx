"use client";

import { DndContext, DragEndEvent, DragOverlay, PointerSensor, useDroppable, useSensor, useSensors } from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { Card, Column } from "@/lib/board";
import * as api from "@/lib/api";
import { dailyQuote, formatDate, getSprintMetrics } from "@/lib/sprint";
import type { Board } from "@/lib/board";
import { AIChatSidebar } from "@/components/AIChatSidebar";
import type { ChatMessage } from "@/lib/chat";

const cardOwner = (columns: Column[], cardId: string) => columns.find((column) => column.cards.some((card) => card.id === cardId))?.id;

function TaskCard({ card, onDelete }: { card: Card; onDelete: (id: string) => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: card.id });
  return <article ref={setNodeRef} style={{ transform: CSS.Transform.toString(transform), transition }} className={`task-card ${isDragging ? "is-dragging" : ""}`} {...attributes} {...listeners}>
    <button className="delete-card" type="button" aria-label={`Delete ${card.title}`} onClick={() => onDelete(card.id)}>×</button>
    <h3>{card.title}</h3><p>{card.details}</p>
  </article>;
}

function ColumnView({ column, onRename, onAdd, onDelete }: { column: Column; onRename: (title: string) => void; onAdd: (title: string, details: string) => void; onDelete: (id: string) => void }) {
  const { setNodeRef, isOver } = useDroppable({ id: column.id });
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(column.title);
  const [adding, setAdding] = useState(false);
  const [title, setTitle] = useState("");
  const [details, setDetails] = useState("");
  function submitRename(event: FormEvent) { event.preventDefault(); onRename(name); setEditing(false); }
  function submitCard(event: FormEvent) { event.preventDefault(); if (!title.trim()) return; onAdd(title.trim(), details.trim()); setTitle(""); setDetails(""); setAdding(false); }

  return <section ref={setNodeRef} className={`kanban-column ${isOver ? "is-over" : ""}`} aria-label={`${column.title} column`}>
    <div className="column-head">
      {editing ? <form onSubmit={submitRename} className="rename-form"><input aria-label="Column name" autoFocus value={name} onChange={(event) => setName(event.target.value)} onBlur={() => { onRename(name); setEditing(false); }} /></form> : <button type="button" className="column-title" onClick={() => { setName(column.title); setEditing(true); }} aria-label={`Rename ${column.title}`}>{column.title}</button>}
      <span className="count">{column.cards.length}</span>
    </div>
    <SortableContext items={column.cards.map((card) => card.id)} strategy={verticalListSortingStrategy}><div className="card-stack">{column.cards.map((card) => <TaskCard card={card} key={card.id} onDelete={onDelete} />)}</div></SortableContext>
    {adding ? <form className="new-card-form" onSubmit={submitCard}>
      <input aria-label="Card title" placeholder="Card title" value={title} onChange={(event) => setTitle(event.target.value)} autoFocus />
      <textarea aria-label="Card details" placeholder="Add a few details" value={details} onChange={(event) => setDetails(event.target.value)} />
      <div><button className="save-card" type="submit">Add card</button><button className="text-button" type="button" onClick={() => setAdding(false)}>Cancel</button></div>
    </form> : <button type="button" className="add-card" onClick={() => setAdding(true)}>+ Add a card</button>}
  </section>;
}

function SprintOverview({ title, onTitleChange }: { title: string; onTitleChange: (title: string) => void }) {
  const today = useMemo(() => new Date(), []);
  const [projectTitle, setProjectTitle] = useState(title);
  const [startDate, setStartDate] = useState("2026-07-21");
  const [deadline, setDeadline] = useState("2026-07-28");
  const [dateError, setDateError] = useState("");
  const metrics = getSprintMetrics(startDate, deadline, today);

  function updateStart(nextStart: string) { if (nextStart > deadline) { setDateError("Start date cannot be later than the deadline."); return; } setStartDate(nextStart); setDateError(""); }
  function updateDeadline(nextDeadline: string) { if (nextDeadline < startDate) { setDateError("Deadline cannot be earlier than the start date."); return; } setDeadline(nextDeadline); setDateError(""); }
  const sprintMessage = metrics.beforeStart ? "Sprint has not started yet." : metrics.completed ? "Sprint completed." : `${metrics.daysRemaining} ${metrics.daysRemaining === 1 ? "day" : "days"} remaining`;

  return <section className="sprint-overview" aria-label="This week sprint overview">
    <div className="sprint-heading"><p className="eyebrow">THIS WEEK</p><input aria-label="Project title" className="project-title" value={projectTitle} onChange={(event) => setProjectTitle(event.target.value)} onBlur={() => onTitleChange(projectTitle)} onKeyDown={(event) => { if (event.key === "Enter") onTitleChange(projectTitle); }} /></div>
    <div className="sprint-content">
      <div className="date-fields"><label>Start<input aria-label="Sprint start date" type="date" value={startDate} onChange={(event) => updateStart(event.target.value)} /></label><label>Deadline<input aria-label="Sprint deadline" type="date" value={deadline} onChange={(event) => updateDeadline(event.target.value)} /></label></div>
      <div className="sprint-metrics"><div><span>SPRINT PROGRESS</span><strong>Day {metrics.currentDay} of {metrics.totalDays}</strong></div><div className="progress-line" aria-label={`${metrics.progress}% complete`}><i style={{ width: `${metrics.progress}%` }} /></div><div className="metric-bottom"><strong>{metrics.progress}% Complete</strong><span className={`status-badge ${metrics.status.toLowerCase()}`}>{metrics.status}</span></div></div>
      <p className="remaining-days">{sprintMessage}</p>
    </div>
    {dateError && <p className="date-error" role="alert">{dateError}</p>}
  </section>;
}

export function KanbanBoard() {
  const [board, setBoard] = useState<Board | null>(null);
  const [error, setError] = useState(false);
  const [activeCard, setActiveCard] = useState<Card | null>(null);
  const [aiOpen, setAiOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));
  const today = useMemo(() => new Date(), []);

  async function load() {
    try { setError(false); setBoard(await api.getBoard()); }
    catch { setError(true); }
  }
  useEffect(() => { void load(); }, []);

  async function withSnapshot<T>(call: () => Promise<Board>): Promise<void> {
    try { setBoard(await call()); }
    catch { void load(); }
  }

  async function handleSendMessage(message: string) {
    const userMessage: ChatMessage = { id: `u-${Date.now()}`, role: "user", content: message };
    setMessages((current) => [...current, userMessage]);
    setAiError(null);
    setAiLoading(true);
    try {
      const { reply, board: snapshot } = await api.aiChat(message);
      const aiMessage: ChatMessage = { id: `a-${Date.now()}`, role: "assistant", content: reply };
      setMessages((current) => [...current, aiMessage]);
      if (snapshot) setBoard(snapshot);
    } catch (err) {
      setAiError(err instanceof Error ? err.message : "AI request failed");
    } finally {
      setAiLoading(false);
    }
  }

  function handleDragEnd({ active, over }: DragEndEvent) {
    setActiveCard(null);
    if (!board || !over || active.id === over.id) return;
    const cardId = String(active.id);
    const targetId = String(over.id);
    const destinationColumn = board.columns.some((column) => column.id === targetId) ? targetId : cardOwner(board.columns, targetId);
    if (!destinationColumn) return;
    const targetIndex = board.columns.find((column) => column.id === destinationColumn)?.cards.findIndex((card) => card.id === targetId);
    void withSnapshot(() => api.moveCard(cardId, destinationColumn, targetIndex === -1 ? undefined : targetIndex));
  }

  async function handleLogout() { await api.logout(); }

  const columns = board?.columns ?? [];

  return <div className={`app-shell ${aiOpen ? "ai-open" : ""}`}>
    <header className="topbar"><a className="brand" href="#board">momentum</a><div className="board-label"><span className="live-dot" />Project board</div><button type="button" className="ai-toggle" aria-label={aiOpen ? "Close AI assistant" : "Open AI assistant"} aria-expanded={aiOpen} onClick={() => setAiOpen((open) => !open)}>{aiOpen ? "Close AI" : "Ask AI"}</button><button type="button" className="logout" onClick={handleLogout}>Sign out</button></header>
    {board ? (
      <>
        <section className="hero"><div><p className="eyebrow">PROJECT SPACE</p><h1>Make progress<br />with intention.</h1><p className="intro">A focused workspace for the work that matters most.</p></div><div className="daily-note"><span>{formatDate(today)}</span><strong>{dailyQuote(today)}</strong></div></section>
        <section id="board" className="board-area" aria-label="Project board">
          <SprintOverview title={board.title} onTitleChange={(title) => { const trimmed = title.trim(); if (trimmed && trimmed !== board.title) void withSnapshot(() => api.updateBoardMeta(trimmed)); }} />
          <div className="board-toolbar"><h2>Board</h2><p className="drag-hint">Drag cards to move them</p></div>
          <DndContext id="project-board" sensors={sensors} onDragStart={({ active }) => setActiveCard(board.columns.flatMap((column) => column.cards).find((card) => card.id === active.id) ?? null)} onDragEnd={handleDragEnd} onDragCancel={() => setActiveCard(null)}>
            <div className="columns">{columns.map((column) => <ColumnView key={column.id} column={column} onRename={(title) => void withSnapshot(() => api.renameColumn(column.id, title))} onAdd={(title, details) => void withSnapshot(() => api.createCard(column.id, title, details))} onDelete={(id) => { setBoard((current) => current ? { ...current, columns: current.columns.map((column) => ({ ...column, cards: column.cards.filter((card) => card.id !== id) })) } : current); void api.deleteCard(id).catch(() => void load()); }} />)}</div>
            <DragOverlay>{activeCard ? <article className="task-card overlay"><h3>{activeCard.title}</h3><p>{activeCard.details}</p></article> : null}</DragOverlay>
          </DndContext>
        </section>
      </>
    ) : error ? (
      <div className="board-status"><p>{"Couldn't load the board."}</p><button type="button" className="text-button" onClick={load}>Retry</button></div>
    ) : (
      <div className="board-status"><p>Loading board…</p></div>
    )}
    <AIChatSidebar open={aiOpen} messages={messages} loading={aiLoading} error={aiError} onClose={() => setAiOpen(false)} onSend={handleSendMessage} />
  </div>;
}