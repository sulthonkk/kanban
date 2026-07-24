import { describe, expect, it } from "vitest";
import { addCard, Column, deleteCard, moveCard, renameColumn } from "./board";

const board: Column[] = [
  { id: "one", title: "One", cards: [{ id: "a", title: "A", details: "" }, { id: "b", title: "B", details: "" }] },
  { id: "two", title: "Two", cards: [] },
];

describe("board state", () => {
  it("renames a column and retains its existing name for blank input", () => { expect(renameColumn(board, "one", "Ideas")[0].title).toBe("Ideas"); expect(renameColumn(board, "one", "  ")[0].title).toBe("One"); });
  it("adds and deletes cards without mutating other cards", () => { const added = addCard(board, "two", { id: "c", title: "C", details: "Details" }); expect(added[1].cards).toHaveLength(1); expect(deleteCard(added, "a")[0].cards.map((card) => card.id)).toEqual(["b"]); });
  it("moves a card between columns and preserves the card", () => { const moved = moveCard(board, "a", "two"); expect(moved[0].cards.map((card) => card.id)).toEqual(["b"]); expect(moved[1].cards.map((card) => card.id)).toEqual(["a"]); });
  it("reorders a card inside its column", () => { expect(moveCard(board, "b", "one", 0)[0].cards.map((card) => card.id)).toEqual(["b", "a"]); });
});
