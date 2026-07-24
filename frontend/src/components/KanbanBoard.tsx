"use client";

import { DndContext, DragEndEvent, DragOverlay, PointerSensor, useDroppable, useSensor, useSensors } from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { FormEvent, useMemo, useState } from "react";
import { addCard, Card, Column, deleteCard, initialColumns, moveCard, renameColumn } from "@/lib/board";
import { dailyQuote, formatDate, getSprintMetrics } from "@/lib/sprint";

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
      {editing ? <form onSubmit={submitRename} className="rename-form"><input aria-label="Column name" autoFocus value={name} onChange={(event) => setName(event.target.value)} onBlur={() => { onRename(name); setEditing(false); }} /></form> : <button type="button" className="column-title" onClick={() => setEditing(true)} aria-label={`Rename ${column.title}`}>{column.title}</button>}
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

function SprintOverview() {
  const today = useMemo(() => new Date(), []);
  const [projectTitle, setProjectTitle] = useState("Project Sprint");
  const [startDate, setStartDate] = useState("2026-07-21");
  const [deadline, setDeadline] = useState("2026-07-28");
  const [dateError, setDateError] = useState("");
  const metrics = getSprintMetrics(startDate, deadline, today);

  function updateStart(nextStart: string) { if (nextStart > deadline) { setDateError("Start date cannot be later than the deadline."); return; } setStartDate(nextStart); setDateError(""); }
  function updateDeadline(nextDeadline: string) { if (nextDeadline < startDate) { setDateError("Deadline cannot be earlier than the start date."); return; } setDeadline(nextDeadline); setDateError(""); }
  const sprintMessage = metrics.beforeStart ? "Sprint has not started yet." : metrics.completed ? "Sprint completed." : `${metrics.daysRemaining} ${metrics.daysRemaining === 1 ? "day" : "days"} remaining`;

  return <section className="sprint-overview" aria-label="This week sprint overview">
    <div className="sprint-heading"><p className="eyebrow">THIS WEEK</p><input aria-label="Project title" className="project-title" value={projectTitle} onChange={(event) => setProjectTitle(event.target.value)} /></div>
    <div className="sprint-content">
      <div className="date-fields"><label>Start<input aria-label="Sprint start date" type="date" value={startDate} onChange={(event) => updateStart(event.target.value)} /></label><label>Deadline<input aria-label="Sprint deadline" type="date" value={deadline} onChange={(event) => updateDeadline(event.target.value)} /></label></div>
      <div className="sprint-metrics"><div><span>SPRINT PROGRESS</span><strong>Day {metrics.currentDay} of {metrics.totalDays}</strong></div><div className="progress-line" aria-label={`${metrics.progress}% complete`}><i style={{ width: `${metrics.progress}%` }} /></div><div className="metric-bottom"><strong>{metrics.progress}% Complete</strong><span className={`status-badge ${metrics.status.toLowerCase()}`}>{metrics.status}</span></div></div>
      <p className="remaining-days">{sprintMessage}</p>
    </div>
    {dateError && <p className="date-error" role="alert">{dateError}</p>}
  </section>;
}

export function KanbanBoard() {
  const [columns, setColumns] = useState<Column[]>(initialColumns);
  const [activeCard, setActiveCard] = useState<Card | null>(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));
  const today = useMemo(() => new Date(), []);

  function handleDragEnd({ active, over }: DragEndEvent) {
    setActiveCard(null); if (!over || active.id === over.id) return;
    const cardId = String(active.id); const targetId = String(over.id);
    const destinationColumn = columns.some((column) => column.id === targetId) ? targetId : cardOwner(columns, targetId);
    if (!destinationColumn) return;
    const targetIndex = columns.find((column) => column.id === destinationColumn)?.cards.findIndex((card) => card.id === targetId);
    setColumns((current) => moveCard(current, cardId, destinationColumn, targetIndex === -1 ? undefined : targetIndex));
  }

  return <div className="app-shell">
    <header className="topbar"><a className="brand" href="#board">momentum</a><div className="board-label"><span className="live-dot" />Project board</div></header>
    <section className="hero"><div><p className="eyebrow">PROJECT SPACE</p><h1>Make progress<br />with intention.</h1><p className="intro">A focused workspace for the work that matters most.</p></div><div className="daily-note"><span>{formatDate(today)}</span><strong>{dailyQuote(today)}</strong></div></section>
    <section id="board" className="board-area" aria-label="Project board">
      <SprintOverview />
      <div className="board-toolbar"><h2>Board</h2><p className="drag-hint">Drag cards to move them</p></div>
      <DndContext id="project-board" sensors={sensors} onDragStart={({ active }) => setActiveCard(columns.flatMap((column) => column.cards).find((card) => card.id === active.id) ?? null)} onDragEnd={handleDragEnd} onDragCancel={() => setActiveCard(null)}>
        <div className="columns">{columns.map((column) => <ColumnView key={column.id} column={column} onRename={(title) => setColumns((current) => renameColumn(current, column.id, title))} onAdd={(title, details) => setColumns((current) => addCard(current, column.id, { id: crypto.randomUUID(), title, details }))} onDelete={(id) => setColumns((current) => deleteCard(current, id))} />)}</div>
        <DragOverlay>{activeCard ? <article className="task-card overlay"><h3>{activeCard.title}</h3><p>{activeCard.details}</p></article> : null}</DragOverlay>
      </DndContext>
    </section>
  </div>;
}
