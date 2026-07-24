export type Card = { id: string; title: string; details: string };
export type Column = { id: string; title: string; cards: Card[] };

export const initialColumns: Column[] = [
  { id: "backlog", title: "Backlog", cards: [{ id: "card-1", title: "Refresh the onboarding", details: "Make the first five minutes feel effortless." }, { id: "card-2", title: "Customer interview notes", details: "Pull out the themes from this week's calls." }] },
  { id: "ready", title: "Ready", cards: [{ id: "card-3", title: "Write launch page copy", details: "Lead with the workflow, not the feature list." }, { id: "card-4", title: "Audit empty states", details: "Give each one a clear and useful next action." }] },
  { id: "progress", title: "In progress", cards: [{ id: "card-5", title: "Polish the project overview", details: "Tighten the hierarchy and status moments." }] },
  { id: "review", title: "In review", cards: [{ id: "card-6", title: "Mobile navigation pass", details: "Check the compact layout at every breakpoint." }] },
  { id: "done", title: "Done", cards: [{ id: "card-7", title: "Define visual direction", details: "Approved: bright, calm, and editorial." }] },
];

export function renameColumn(columns: Column[], columnId: string, title: string) {
  return columns.map((column) => column.id === columnId ? { ...column, title: title.trim() || column.title } : column);
}

export function addCard(columns: Column[], columnId: string, card: Card) {
  return columns.map((column) => column.id === columnId ? { ...column, cards: [...column.cards, card] } : column);
}

export function deleteCard(columns: Column[], cardId: string) {
  return columns.map((column) => ({ ...column, cards: column.cards.filter((card) => card.id !== cardId) }));
}

export function moveCard(columns: Column[], cardId: string, destinationColumnId: string, destinationIndex?: number) {
  const sourceColumn = columns.find((column) => column.cards.some((card) => card.id === cardId));
  const card = sourceColumn?.cards.find((item) => item.id === cardId);
  if (!sourceColumn || !card) return columns;
  const sourceCards = sourceColumn.cards.filter((item) => item.id !== cardId);
  return columns.map((column) => {
    if (column.id === sourceColumn.id && column.id === destinationColumnId) {
      const index = Math.min(destinationIndex ?? sourceCards.length, sourceCards.length);
      return { ...column, cards: [...sourceCards.slice(0, index), card, ...sourceCards.slice(index)] };
    }
    if (column.id === sourceColumn.id) return { ...column, cards: sourceCards };
    if (column.id === destinationColumnId) {
      const index = Math.min(destinationIndex ?? column.cards.length, column.cards.length);
      return { ...column, cards: [...column.cards.slice(0, index), card, ...column.cards.slice(index)] };
    }
    return column;
  });
}
