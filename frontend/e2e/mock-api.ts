import type { Page, Route } from "@playwright/test";
import { addCard, deleteCard, moveCard, renameColumn } from "../src/lib/board";
import type { Board } from "../src/lib/board";

// Seed board mirrors the backend seed (backend/app/db.py) and the original
// frontend/src/lib/board.ts initialColumns so existing assertions keep working.
const SEED_BOARD: Board = {
  id: "seed-board",
  title: "Project board",
  columns: [
    { id: "backlog", title: "Backlog", cards: [{ id: "card-1", title: "Refresh the onboarding", details: "Make the first five minutes feel effortless." }, { id: "card-2", title: "Customer interview notes", details: "Pull out the themes from this week's calls." }] },
    { id: "ready", title: "Ready", cards: [{ id: "card-3", title: "Write launch page copy", details: "Lead with the workflow, not the feature list." }, { id: "card-4", title: "Audit empty states", details: "Give each one a clear and useful next action." }] },
    { id: "progress", title: "In progress", cards: [{ id: "card-5", title: "Polish the project overview", details: "Tighten the hierarchy and status moments." }] },
    { id: "review", title: "In review", cards: [{ id: "card-6", title: "Mobile navigation pass", details: "Check the compact layout at every breakpoint." }] },
    { id: "done", title: "Done", cards: [{ id: "card-7", title: "Define visual direction", details: "Approved: bright, calm, and editorial." }] },
  ],
};

const LOGIN_HTML = '<!doctype html><html><body><h1>Sign in</h1><form action="/api/login" method="post"><input name="username"/><input name="password" type="password"/><button type="submit">Sign in</button></form></body></html>';

function json(route: Route, status: number, body: unknown) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

function newId(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

// Pull the {id} segment out of a /api/.../{id}[/...] URL.
function idIn(url: string, index: number): string {
  return new URL(url).pathname.split("/")[index];
}

export async function installMockApi(page: Page, opts: { authed?: boolean } = {}): Promise<void> {
  const authed = opts.authed ?? true;
  let board: Board = JSON.parse(JSON.stringify(SEED_BOARD));

  await page.route("**/api/board", (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    if (!authed) return route.fulfill({ status: 401, contentType: "application/json", body: '{"detail":"not authenticated"}' });
    return json(route, 200, board);
  });

  await page.route("**/api/board/meta", (route) => {
    if (route.request().method() !== "PUT") return route.fallback();
    const body = route.request().postDataJSON() ?? {};
    board = { ...board, title: body.title };
    return json(route, 200, board);
  });

  await page.route("**/api/columns/*/rename", (route) => {
    const body = route.request().postDataJSON() ?? {};
    const columnId = idIn(route.request().url(), 3);
    board = { ...board, columns: renameColumn(board.columns, columnId, body.title) };
    return json(route, 200, board);
  });

  await page.route("**/api/cards", (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    const body = route.request().postDataJSON() ?? {};
    board = { ...board, columns: addCard(board.columns, body.column_id, { id: newId(), title: body.title, details: body.details ?? "" }) };
    return json(route, 201, board);
  });

  await page.route("**/api/cards/*/move", (route) => {
    const body = route.request().postDataJSON() ?? {};
    board = { ...board, columns: moveCard(board.columns, idIn(route.request().url(), 3), body.column_id, body.index) };
    return json(route, 200, board);
  });

  await page.route("**/api/cards/*", (route) => {
    if (route.request().method() !== "DELETE") return route.fallback();
    board = { ...board, columns: deleteCard(board.columns, idIn(route.request().url(), 3)) };
    return route.fulfill({ status: 204 });
  });

  await page.route("**/api/logout", (route) => route.fulfill({ status: 303, headers: { location: "/login" }, body: "" }));

  await page.route("**/login", (route) => route.fulfill({ status: 200, contentType: "text/html", body: LOGIN_HTML }));
}

export async function installMockApiUnauthorized(page: Page): Promise<void> {
  await page.route("**/api/board", (route) => route.fulfill({ status: 401, contentType: "application/json", body: '{"detail":"not authenticated"}' }));
  await page.route("**/login", (route) => route.fulfill({ status: 200, contentType: "text/html", body: LOGIN_HTML }));
}