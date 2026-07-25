import type { Board } from "@/lib/board";

const API_BASE = "/api";
const JSON_HEADERS = { "content-type": "application/json", accept: "application/json" };

function goToLogin(): never {
  if (typeof window !== "undefined") window.location.assign("/login");
  throw new Error("session expired");
}

async function read<T>(response: Response): Promise<T> {
  if (response.type === "opaqueredirect" || response.status === 401) goToLogin();
  if (response.status === 204) return undefined as unknown as T;
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return (await response.json()) as T;
}

function post(url: string, body: unknown): Promise<Response> {
  return fetch(`${API_BASE}${url}`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
    redirect: "manual",
    credentials: "same-origin",
  });
}

export async function getBoard(): Promise<Board> {
  const response = await fetch(`${API_BASE}/board`, {
    headers: { accept: "application/json" },
    redirect: "manual",
    credentials: "same-origin",
  });
  return read<Board>(response);
}

export async function renameColumn(columnId: string, title: string): Promise<Board> {
  return read<Board>(await post(`/columns/${columnId}/rename`, { title }));
}

export async function createCard(columnId: string, title: string, details: string): Promise<Board> {
  return read<Board>(await post(`/cards`, { column_id: columnId, title, details }));
}

export async function deleteCard(cardId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/cards/${cardId}`, {
    method: "DELETE",
    headers: { accept: "application/json" },
    redirect: "manual",
    credentials: "same-origin",
  });
  await read<void>(response);
}

export async function moveCard(
  cardId: string,
  columnId: string,
  index: number | undefined
): Promise<Board> {
  return read<Board>(await post(`/cards/${cardId}/move`, { column_id: columnId, index }));
}

export async function updateBoardMeta(title: string): Promise<Board> {
  const response = await fetch(`${API_BASE}/board/meta`, {
    method: "PUT",
    headers: JSON_HEADERS,
    body: JSON.stringify({ title }),
    redirect: "manual",
    credentials: "same-origin",
  });
  return read<Board>(response);
}

export async function logout(): Promise<void> {
  await fetch(`${API_BASE}/logout`, {
    method: "POST",
    headers: { accept: "application/json" },
    redirect: "manual",
    credentials: "same-origin",
  }).catch(() => {});
  if (typeof window !== "undefined") window.location.assign("/login");
}